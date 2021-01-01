import re,itertools
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("output_file")

args = parser.parse_args()

def multimatch(line_slice,regexes):
    result = []
    for line,regex in zip(line_slice,regexes):
        m = regex.match(line)
        if m:
            result.append(m)
        else:
            break
    else:
        return result
    return None

regexes = [((
r"move.*\s+#\$4EF9,(\$\w+)",
r"pea\s+(\w+)\(pc\)",
r"move\.l\s+\([AS][7P]\)\+,(\$\w+)"),"PL_P\t\\1,\\2"
),
((
r"move.*\s+#\$4EF9,(\$\w+)",
r"pea\s+(\w+)",
r"move\.l\s+\([AS][7P]\)\+,(\$\w+)"),"PL_P\t\\1,\\2"
),
((
r"move.*\s+#\$4EB9,(\$\w+)",
r"pea\s+(\w+)\(pc\)",
r"move\.l\s+\([AS][7P]\)\+,(\$\w+)"),"PL_PS\t\\1,\\2"
),
((
r"move.*\s+#\$4EB9,(\$\w+)",
r"pea\s+(\w+)",
r"move\.l\s+\([AS][7P]\)\+,(\$\w+)"),"PL_PS\t\\1,\\2"
),
((
r"move.*\s+#\$4E714EB9,(\$\w+)",
r"pea\s+(\w+)\(pc\)",
r"move\.l\s+\([AS][7P]\)\+,(\$\w+)"),"PL_PSS\t\\1,\\2,2"
),
((
r"pea\s+(\w+)\(pc\)",
r"move\.l\s+\([AS][7P]\)\+,(\$\w+)"),"PL_PA\t\\2,\\1"
),
((
r"move\.w\s+#\$4E75,(\$\w+).?W?",
),"PL_R\t\\1"
),
((
r"move\.w\s+#\$4E71,(\$\w+).?W?",
),"PL_NOP\t\\1,2"
),
((
r"move\.l\s+#\$4E714E71,(\$\w+).?W?",
),"PL_NOP\t\\1,4"
),
((
r"move\.w\s+#(\$?\w+),(\$\w+).?W?",
),"PL_W\t\\2,\\1"
),
((
r"move\.b\s+#(\$?\w+),(\$\w+)",
),"PL_B\t\\2,\\1"
),
((
r"move\.l\s+#(\$?\w+),(\$\w+)",
),"PL_L\t\\2,\\1"
),
((
r"(PATCHUSRJMP|patch)\s+(\$?\w+)\.?W?,(\w+)",
),"PL_P\t\\2,\\3"
),
((
r"(PATCHUSRJSR|patchs)\s+(\$?\w+)\.?W?,(\w+)",
),"PL_PS\t\\2,\\3"
),
]

regexes = [(re.compile(".*\n\s+".join(s),re.IGNORECASE),r) for s,r in regexes]

def getslice(i):
    return itertools.islice(lines,i)

with open(args.input_file) as f:
    lines = f.read()
    for s,r in regexes:
        lines = s.sub(r,lines)

with open(args.output_file,"w") as f:
    f.write(lines)


