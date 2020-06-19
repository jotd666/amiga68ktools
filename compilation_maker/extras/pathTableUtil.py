#!/usr/bin/env python

import sys
import struct
from collections import deque

if len(sys.argv) == 3 and sys.argv[1] in ("print", "uppercase"):
	operation = sys.argv[1]

	isoFile = open(sys.argv[2], "rb")
	if "uppercase" == operation:
		isoFile = open(sys.argv[2], "rb+")
else:
	raise SystemExit("Usage: " + sys.argv[0].split('/')[-1] + " operation (print/uppercase) isoFile")

sectorSize = 2048

isoFile.seek(sectorSize * 0x10)

class DirectoryEntry:
	def __init__(self, data):
		self.headerLength = 33
		self.recordLen, self.extRecordLen, self.extentLoc, self.extentDataLen, self.timestamp, self.flags, self.unitFlags, self.gapSize, self.volSeqNum, self.fileIdLen = struct.unpack(">BB4xI4xI7sBBB2xHB", data[:self.headerLength])
		self.data = data[:self.recordLen]
		self.fileId = self.data[self.headerLength:self.headerLength + self.fileIdLen]

	def isEmpty(self):
		return 0 == self.recordLen

	def __repr__(self):
		return ",".join([self.fileId, str(self.recordLen)])

class PrimaryVolumeDescriptor:
	def __init__(self, volumeDescriptorData):
		self.logicalBlockSize, self.pathTableSize, self.pathTableLocMSB = struct.unpack(">2xH4xI8xI", volumeDescriptorData[128:128 + 4 + 8 + 8 + 4])
		self.pathTableLocLSB = struct.unpack("<I", volumeDescriptorData[140:140 + 4])[0]
		self.rootDirEntry = DirectoryEntry(volumeDescriptorData[156:156 + 34])

def getPrimaryVolumeDescriptor(isoFile):
	terminatorCode = 255
	primaryVolumeDescriptorCode = 1
	while True:
		volumeDescriptorData = isoFile.read(sectorSize)
		volumeDescriptorCode = struct.unpack("B", volumeDescriptorData[0:1])[0]

		if volumeDescriptorCode == terminatorCode:
			return None
		elif volumeDescriptorCode == primaryVolumeDescriptorCode:
			return PrimaryVolumeDescriptor(volumeDescriptorData)


class PathTableEntry:
	def __init__(self, entryDataStart, littleEndian, position):
		self.littleEndian = littleEndian
		self.position = position
		self.headerLength = 8
		nameLen, self.extentLen, self.extentLoc, self.parentNum = struct.unpack(self.getHeaderStruct(), entryDataStart[:self.headerLength])
		self.name = entryDataStart[self.headerLength:self.headerLength + nameLen]
		self.children = []

	def __repr__(self):
		return self.name + "'," + ",".join((str(self.parentNum), str(self.position), str(self.getSize())))

	def getHeaderStruct(self):
		headerStruct = "BBIH"
		if self.littleEndian:
			return "<" + headerStruct
		else:
			return ">" + headerStruct

	def getSize(self):
		nameLen = len(self.name)
		return self.headerLength + nameLen + nameLen % 2

	def getRangeString(self):
		start = self.position
		end = start + self.getSize() - 1
		return "{0:05d}-{1:05d}".format(start, end)

	def isRoot(self):
		# The root will point to itself
		return self == self.parent

	def getAsData(self):
		nameLen = len(self.name)
		completeStruct = self.getHeaderStruct() + str(nameLen) + "s" + str(nameLen % 2) + "x"
		data = struct.pack(completeStruct, nameLen, self.extentLen, self.extentLoc, self.parentNum, self.name)
		return data

	def getParents(self):
		parents = []
		currParent = self.parent
		while not currParent.isRoot():
			parents.append(currParent)
			currParent = currParent.parent

		parents.reverse()
		return parents


def breadthFirstWalker(rootNode):
	queue = deque()
	queue.appendleft(rootNode)
	while 0 != len(queue):
		node = queue.pop()
		queue.extendleft(node.children)
		yield node

class PathTable:
    def __init__(self, pathTableData, littleEndian):
    	self.littleEndian = littleEndian
    	self.entries = []
    	headerLength = 8
    	currentPos = 0
    	while currentPos < descriptor.pathTableSize:
    		entry = PathTableEntry(pathTableData[currentPos:], self.littleEndian, currentPos)
    		self.entries.append(entry)
    		currentPos = currentPos + entry.getSize()

    	# Setup real parent links, which will survive a list sort
    	for entry in self.entries:
    		entry.parent = self.entries[entry.parentNum - 1]
    		if entry != entry.parent: # Avoid the root being its own child also, makes it harder to walk the graph :)
    			entry.parent.children.append(entry)

    def getRootEntry(self):
    	return self.entries[0]

    def getNonRootEntries(self):
    	return self.entries[1:]

    def upperCaseEntries(self):
    	for entry in self.entries:
    		entry.name = entry.name.upper()

    def updateParentNums(self):
    	for i, entry in enumerate(self.entries):
    		for child in entry.children:
    			child.parentNum = i + 1

    def sortEntries(self):
    	for entry in self.entries:
    		entry.children.sort(key=lambda e: e.name)

    	self.entries = [e for e in breadthFirstWalker(self.getRootEntry())]

    	self.updateParentNums()

    def getEntriesAsData(self):
        data = b""
        for entry in self.entries:
            data += entry.getAsData()
        return data

    def printEntries(self):
        for entry in self.entries:
            pathElements = [e.name for e in entry.getParents() + [entry]]
            print(entry.getRangeString() + "(" + str(len(pathElements)) + "): " + '/'.join(x.decode("latin-1") for x in pathElements))



descriptor = getPrimaryVolumeDescriptor(isoFile)
print("PathTable size: {}".format(descriptor.pathTableSize))

def sortDirEntriesUppercased(descriptor, pathTableEntry):
	isoFile.seek(pathTableEntry.extentLoc * descriptor.logicalBlockSize)
	extentData = isoFile.read(descriptor.logicalBlockSize)
	dirEntry = DirectoryEntry(extentData)
	extentData += isoFile.read(max(0, dirEntry.extentDataLen - descriptor.logicalBlockSize))
	currentPos = dirEntry.recordLen
	parentDirEntry = DirectoryEntry(extentData[currentPos:])
	currentPos += parentDirEntry.recordLen
	childDirEntries = []
	while currentPos <  dirEntry.extentDataLen - 33:
		childDirEntry = DirectoryEntry(extentData[currentPos:])
		currentPos += childDirEntry.recordLen
		if childDirEntry.isEmpty():
			spaceLeftInBlock = descriptor.logicalBlockSize - (currentPos % descriptor.logicalBlockSize)
			currentPos += spaceLeftInBlock
			continue
		childDirEntries.append(childDirEntry)

	isoFile.seek(pathTableEntry.extentLoc * descriptor.logicalBlockSize)
	currentPos = 0
	for dirEntry in [dirEntry, parentDirEntry] + sorted(childDirEntries, key=lambda e: e.fileId.rsplit(b";",1)[0].upper()):
		spaceLeftInBlock = descriptor.logicalBlockSize - (currentPos % descriptor.logicalBlockSize)
		if len(dirEntry.data) > spaceLeftInBlock:
			isoFile.write(b'\0' * spaceLeftInBlock)
			currentPos += spaceLeftInBlock
		isoFile.write(dirEntry.data)
		currentPos += len(dirEntry.data)

	spaceLeftInBlock = descriptor.logicalBlockSize - (currentPos % descriptor.logicalBlockSize)
	isoFile.write(b'\0' * spaceLeftInBlock)

# Big endian path table is what is used on the CD32
isoFile.seek(descriptor.pathTableLocMSB * descriptor.logicalBlockSize)
pathTableMSB = PathTable(isoFile.read(descriptor.pathTableSize), False)

# Also process the little endian path table for completeness sake
isoFile.seek(descriptor.pathTableLocLSB * descriptor.logicalBlockSize)
pathTableLSB = PathTable(isoFile.read(descriptor.pathTableSize), True)

# Test comparison
#isoFile.seek(descriptor.pathTableLocMSB * descriptor.logicalBlockSize)
#pathTableMSBData = isoFile.read(descriptor.pathTableSize)
#testDataMSB = pathTableMSB.getEntriesAsData()
#print "TestDataMSBLength:", len(testDataMSB)
#print "MatchMSB:", pathTableMSBData == testDataMSB

if "uppercase" == operation:
	pathTableMSB.upperCaseEntries()
	pathTableMSB.sortEntries()
	isoFile.seek(descriptor.pathTableLocMSB * descriptor.logicalBlockSize)
	isoFile.write(pathTableMSB.getEntriesAsData())
	print("Uppercased and resorted MSB path table!")

	pathTableLSB.upperCaseEntries()
	pathTableLSB.sortEntries()
	isoFile.seek(descriptor.pathTableLocLSB * descriptor.logicalBlockSize)
	isoFile.write(pathTableLSB.getEntriesAsData())
	print("Uppercased and resorted LSB path table!")

	for entry in pathTableMSB.entries:
		sortDirEntriesUppercased(descriptor, entry)
	print("Sorted directory entries in uppercased name order!")

isoFile.close()

if "print" == operation:
	pathTableMSB.printEntries()

