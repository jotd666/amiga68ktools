wx_available = False
__empty_app = None
try:
    import wx
    wx_available = True
    __empty_app = wx.App(redirect=False)
except ImportError as e:
    # no wx
    #print("wx_utils: "+str(e)+" Switching to degraded mode")
    import wx_dummy as wx

import os,sys,time,traceback
import collections
import fnmatch
import threading
import logging

import python_lacks,eve
import threading


class BigListChoice(wx.Dialog):
    __MODULE_FILE = __file__
    __PROGRAM_DIR = os.path.dirname(__MODULE_FILE)

    def __init__(self, parent, title, items):
        import wx.lib.buttons
        wx.Dialog.__init__(self, id=wx.NewId(), name=u'SelectVddDlg',
              parent=parent, pos=wx.Point(525, 200), size=wx.Size(320, 210),
              style=wx.DEFAULT_DIALOG_STYLE, title=title)
        self.SetClientSize(wx.Size(320, 210))

        self.__selected_item = None
        self.__items = items

        #Declaration of static text
        static_text = wx.StaticText(id=wx.NewId(),
              label=u'type here', name=u'__vdd_name', parent=self,
              pos=wx.Point(12, 10), size=wx.Size(70, 20), style=0)

        #Declaration of control text
        nid = wx.NewId()
        self.__text_selection = wx.TextCtrl(id=nid,
              value=u'',name=u'__vdd_name_selection',parent=self,
              pos=wx.Point(85,10),size=wx.Size(200,20),style=wx.TE_PROCESS_ENTER)
        self.__text_selection.Bind(wx.EVT_TEXT,self.__filter_list,id=nid)
        self.__text_selection.Bind(wx.EVT_KEY_DOWN,self.__go_to_choices,id=nid)
        self.__text_selection.Bind(wx.EVT_TEXT_ENTER,self.__on_choice_enter,id=nid)

        #Declaration of list box
        nid = wx.NewId()
        self.__choices = wx.ListCtrl(id=nid, name=u'vdd_version', parent=self,
              pos=wx.Point(12, 35), size=wx.Size(296, 128), style=wx.LC_NO_HEADER|wx.LC_REPORT)
        self.__choices.Bind(wx.EVT_LISTBOX_DCLICK,
              self.__on_choice_double_click, id=nid)
        self.__choices.Bind(wx.EVT_LIST_ITEM_ACTIVATED,self.__on_choice_double_click,id=nid)
        self.__populate_list(self.__items)

        #Declaration of buttons
        nid = wx.NewId()
        self.__select_button = wx.Button(id=nid, label=u'Select',
              name=u'select_button', parent=self, pos=wx.Point(72, 176),
              size=wx.Size(75, 23), style=0)
        self.__select_button.Bind(wx.EVT_BUTTON, self.__on_choice_double_click,
              id=nid)

        self.__cancel = wx.Button(id=wx.ID_CANCEL, label=u'Cancel',
              name=u'cancel', parent=self, pos=wx.Point(172, 176),
              size=wx.Size(75, 23), style=0)
        self.__cancel.Bind(wx.EVT_BUTTON,self.__close,id=wx.ID_CANCEL)

        #Declaration of bitmap button
        picture = wx.Bitmap(os.path.join(self.__PROGRAM_DIR,'delete.png'))
        nid = wx.NewId()
        self.__delete_pattern_button = wx.lib.buttons.GenBitmapButton(bitmap=picture, id=nid,
              name=u'__delete_pattern', parent=self, pos=wx.Point(287, 10), size=wx.Size(20, 20), style=0)
        self.__delete_pattern_button.SetToolTipString(u'Clear pattern')
        self.__delete_pattern_button.Bind(wx.EVT_BUTTON,self.__delete_pattern,id=nid)
##        self.close_Button.SetCursor(wx.StockCursor(wx.CURSOR_HAND))

    def __populate_list(self,items):
        self.__choices.ClearAll()
        self.__choices.InsertColumn(0,"ID")
        self.__choices.SetColumnWidth(0, 256)
        for i in items:
            self.__choices.Append([i])

    def __go_to_choices(self,event):
        code = event.GetKeyCode()
        if code == wx.WXK_DOWN:
            self.__choices.SetFocus()
            if self.__choices.GetItemCount() != 0 :
                self.__choices.Select(0)
        else:
            event.Skip()

    def get_selected_item(self):
        return self.__selected_item

    def __close(self,event):
        event.Skip()
        self.__selected_item = None
        self.Destroy()

    def __on_choice_double_click(self, event):
        event.Skip()
        sitems = get_selected_items(self.__choices)
        if len(sitems)>0:
            self.__selected_item = sitems[0]
            self.Destroy()

    def __on_choice_enter(self,event):
        event.Skip()
        if self.__choices.GetItemCount() == 1 :
            self.__selected_item = self.__choices.GetItem(0).GetText()
            self.Destroy()

    def __delete_pattern(self,event):
        event.Skip()
        self.__text_selection.ChangeValue("")
        self.__populate_list(self.__items)

    def __filter_list(self,event):
        event.Skip()
        vdd_name = self.__text_selection.GetValue()
        if self.__items != [] :
            #Check if vdd name is empty to add items
            if vdd_name != "" :
                #Clear listbox
                filter_list = []
                pattern = "*" + vdd_name+"*"
                for l in self.__items:
                    if fnmatch.fnmatch(l,pattern):
                        filter_list.append(l)
                self.__populate_list(filter_list)
            else:
                self.__populate_list(self.__items)


DROPMODE_FILENAME = 0
DROPMODE_FILELIST = 1
DROPMODE_FILELIST_APPEND = 2
DROPMODE_FILECONTENTS = 3
DROPMODE_FILECONTENTS_APPEND = 4
DROPMODE_CUSTOM = 5  # set this with a non-None "post_operation" for totally custom stuff

def enable_filename_drop(target_window,mode=DROPMODE_FILENAME,trans_function=str,post_operation=None):
    """
    configure target_window so drag/drop a file/dir icon on it sets
    the full filepath in the window
    using SetValue allows to trigger "text" event. using ChangeValue wouldn't
    do this
    post_operation: if not None, function will be called with filenames as sole parameter
    """
    class MyFileDropTarget(wx.FileDropTarget):
        def __init__(self):
            wx.FileDropTarget.__init__(self)
            self.__window = target_window
            self.__window.SetDropTarget(self)
            self.__mode = mode
            self.__trans_function = trans_function
            self.__post_operation = post_operation

        def OnDropFiles(self, x, y, filenames):
            fn2 = []
            for f in filenames:
                fn2.append(self.__trans_function(f))

            if self.__mode == DROPMODE_FILENAME:
                self.__window.SetValue(fn2[0])
            elif self.__mode == DROPMODE_FILELIST:
                self.__window.SetItems(fn2)
            elif self.__mode == DROPMODE_FILECONTENTS_APPEND:
                if isinstance(self.__window,wx.ListCtrl):
                    fc=[]
                    # safety: consider only lines with "@"
                    for f in fn2:
                        filesize = os.path.getsize(f)
                        # safety to avoid dropping a huge file by mistake
                        if filesize < 1000000:
                            fc += filter(lambda x: "@" in x, python_lacks.read_file(f))
                    # ATM limited to 1 column
                    for f in fc:
                        self.__window.Append([f])
                else:
                    self.__window.AppendItems(fc)

            elif self.__mode == DROPMODE_FILELIST_APPEND:
                if isinstance(self.__window,wx.ListCtrl):
                    # ATM limited to 1 column
                    for f in fn2:
                        self.__window.Append([f])
                else:
                    self.__window.AppendItems(fn2)
            elif self.__mode == DROPMODE_FILECONTENTS:
                # fill textfield (better if multi-line) with file(s) contents
                txt = ""
                for f in filenames:
                    filesize = os.path.getsize(f)
                    # safety to avoid dropping a huge file by mistake
                    if filesize < 1000000:
                        h = open(f,"rb")
                        txt += h.read()
                        if not txt.endswith("\n"):
                            txt += "\n"
                        h.close()
                self.__window.SetValue(txt)
            if self.__post_operation != None:
                self.__post_operation(filenames)

    MyFileDropTarget()


def info_banner(message,title="Information",parent=None,nb_max_lines=30,time=5000):
    """
    Create a Dialog with a message. This dialog will be closed after the timer out
    """
    def create(parent,message,title,time):
        return InfoBanner(parent,time, message, title)

    [wxID___INFO_BANNER,wxID___INFO_BANNER__OK_BUTTON,wxID___INFO_BANNER__ICON,wxID___INFO_BANNER__INFO_TEXT ]=[wx.NewId() for _init_ctrls in range(4)]

    class InfoBanner(wx.Dialog):
        def _init_ctrls(self,p,time):
            wx.Dialog.__init__(self,id=wxID___INFO_BANNER,name=u'__info_banner',
                parent= p, pos=wx.Point(400,300),size=wx.Size(250,100),
                style=wx.DEFAULT_DIALOG_STYLE,title="Information")
            self.SetClientSize(wx.Size(250,100))
            self.SetHelpText(u'')

            self.__ok_button = wx.Button(id=wxID___INFO_BANNER__OK_BUTTON,label=u'Ok', name=u'__ok_button', parent=self, style=0)
            self.__ok_button.Bind(wx.EVT_BUTTON,self.__on_close,id=wxID___INFO_BANNER__OK_BUTTON)

            self.__info_text = wx.StaticText(id=wxID___INFO_BANNER__INFO_TEXT,name=u'__info_test',parent=self,style=0)

            self.__picture = wx.StaticBitmap(id=wxID___INFO_BANNER__ICON, name=u'__picture',parent=self, style=0)

            #Declaration of Boxes Layout
            vbox_north = wx.BoxSizer(wx.HORIZONTAL)
            vbox_north.Add(self.__picture,flag=wx.LEFT|wx.RIGHT|wx.TOP,border=5)
            vbox_north.Add(self.__info_text,flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT,border=10)

            vbox_all = wx.BoxSizer(wx.VERTICAL)
            vbox_all.Add(vbox_north)
            vbox_all.Add(self.__ok_button,flag=wx.ALL|wx.CENTER|wx.BOTTOM,border=10)

            self.SetSizer(vbox_all)

            #Declaration and beggining of the timer
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER,self.__on_close,self.timer)
            self.timer.Start(time)

        def __init__(self,parent, time, message, title):
            self._init_ctrls(parent, time)
            self.SetTitle(title)
            self.__picture.SetBitmap(bitmap=wx.ArtProvider_GetBitmap(wx.ART_INFORMATION))
            self.__info_text.SetLabel(message)
            self.Fit()

        def __on_close(self,event):
            self.Destroy()

    message = __truncate_message(message,nb_max_lines)
    i = create(parent,message,title,time)
    i.ShowModal()

def send_to(method,parent,path_picture=None):
    """
    Create a menu "send to" with favorite shortcuts
    method = Method of shorcuts for bind
    parent = Parent frame for bind
    path_picture = the path of pictures to show in submenu (not required)
    """
    class SendToSubMenu(wx.Menu):
        def __init__(self):
            wx.Menu.__init__(self)
            env = os.getenv("USERPROFILE")
            self.__user_path =  os.path.join(env,r"AppData\Roaming\Microsoft\Windows\SendTo")
            if not os.path.exists(self.__user_path):
                self.__user_path = os.path.join(env,"SendTo")

            self.__shortcuts_send_to = dict()
            self.__path_picture = path_picture
            self.__method = method
            self.__list_send_to()
            self.__on_right_click_menu()

        def __list_send_to(self):
                list_dir = []
                #Creation of list with different shortcuts
                for roots, dirs, files in os.walk(self.__user_path):
                    #Creation of list with different submenu in Send To submenu
                    for d in dirs:
                        list_dir.append(d)
                    for f in files:
                        #Add first level shortcuts
                        file_name = f.replace(f[0], f[0].upper(), 1)
                        if os.path.exists(os.path.join(self.__user_path,f)):
                            self.__shortcuts_send_to[file_name] = self.__user_path
                        else:
                            #Add second level shortcuts
                            for d in list_dir:
                                path = os.path.join(self.__user_path,d,f)
                                if os.path.exists(path):
                                    self.__shortcuts_send_to[file_name] = os.path.dirname(path)

        def __icon_shortcut(self,abs_path):
            size = os.path.getsize(abs_path)
            picture = None
            if size > 0:
                if fnmatch.fnmatch(abs_path,"*.bat"):
                    #Add defautl icon for .bat
                    image = wx.Image(os.path.join(self.__path_picture,"bat.gif"), wx.BITMAP_TYPE_ANY)
                    picture = wx.BitmapFromImage(image)
                else:
                    #Check if shortcuts is a .lnk file
                    if fnmatch.fnmatch(abs_path,"*.lnk"):
                        import win32com.client

                        shell = win32com.client.Dispatch("WScript.Shell")
                        try :
                            shortcut = shell.CreateShortCut(abs_path)
                            if os.path.exists(shortcut.Targetpath):
                                    il = wx.IconLocation(shortcut.Targetpath,0)
                                    if il.IsOk():
                                        #Deactivate flag error message
                                        wx.Log_EnableLogging(False)
                                        icon = wx.IconFromLocation(il)
                                        #Reactivate flag error message
                                        wx.Log_EnableLogging(True)
                                        if icon.Ok() :
                                            bmp = wx.EmptyBitmap(1,1)
                                            bmp.CopyFromIcon(icon)

                                            img = wx.ImageFromBitmap(bmp)
                                            img = img.Scale(bmp.GetWidth()//2,bmp.GetHeight()//2, wx.IMAGE_QUALITY_HIGH)
                                            picture = wx.BitmapFromImage(img)
                        except Exception as e:
                            # sometimes cannot load the image
                            print(str(e))
            if picture == None:
                #Add default icon
                image = wx.Image(os.path.join(self.__path_picture,"default.png"), wx.BITMAP_TYPE_ANY)
                picture = wx.BitmapFromImage(image)
            return picture

        def __on_right_click_menu(self):
                #Submenu of send to
                self.__send_to = wx.Menu()
                s_keys = self.__shortcuts_send_to.keys()
                s_keys.sort()
                dir_submenu = collections.defaultdict(list)
                for k in s_keys:
                    #Add first level shortcuts in Send To submenu
                    if self.__shortcuts_send_to[k] == self.__user_path :
                        name_shorcut = k.split('.')
                        self.__popup_menu = wx.NewId()
                        item = wx.MenuItem(self.__send_to,self.__popup_menu,name_shorcut[0])
                        if self.__path_picture != None :
                            #Loading picture of shortcuts
                            abs_path = (os.path.join(self.__user_path,k))
                            picture = self.__icon_shortcut(abs_path)
                            item.SetBitmap(picture)
                        self.__send_to.AppendItem(item)
                        parent.Bind(wx.EVT_MENU,self.__method,id=self.__popup_menu)
                    else:
                        #Construction of different dirs in Send To submenu
                        name_dir = os.path.basename(self.__shortcuts_send_to[k])
                        dir_submenu[name_dir].append(k)

                #Construction of sub menu in sub menu Send To
                d_keys = dir_submenu.keys()
                d_keys.sort()
                for d in d_keys:
                    self.__popup_menu = wx.NewId()
                    self.__submenu_sub = wx.Menu()
                    #Add second level shortcuts in submenu
                    for v in dir_submenu[d]:
                        self.__popup_submenu = wx.NewId()
                        item_sub = wx.MenuItem(self.__submenu_sub,self.__popup_submenu,str(v))
                        if self.__path_picture != None:
                            abs_path = (os.path.join(self.__user_path,d,v))
                            picture = self.__icon_shortcut(abs_path)
                            item_sub.SetBitmap(picture)
                        parent.Bind(wx.EVT_MENU,self.__method,id=self.__popup_submenu)
                        self.__submenu_sub.AppendItem(item_sub)
                    #Add dirs submenu in Send To submenu
                    self.__send_to.AppendMenu(self.__popup_menu,str(d),self.__submenu_sub)

        def return_menu(self) :
            return self.__send_to

        def return_shortcuts(self):
            return self.__shortcuts_send_to

        def return_user_path(self):
            return self.__user_path

    t = SendToSubMenu()
    return [t.return_menu(),t.return_shortcuts(),t.return_user_path()]

def __truncate_message(msg,nb_max_lines,nb_max_line_size=1000):
    # create truncated lines
    lines = [l if len(l)<nb_max_line_size else l[:nb_max_line_size]+"..." for l in msg.splitlines()]
    if len(lines) > nb_max_lines:
        lines = lines[0:nb_max_lines]+["..."]

    msg = "\n".join(lines)
    msg = python_lacks.ascii_compliant(msg,best_ascii_approximation=True)
    return msg

def error_message(message,title="Error",parent=None,nb_max_lines=30,nb_max_line_size=200):
    message = __truncate_message(message,nb_max_lines,nb_max_line_size)
    if wx_available:
        dlg = wx.MessageDialog(parent, message,  title, wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()
    else:
        print(title+": "+message)

def info_message(message,title="Information",parent=None,nb_max_lines=30):
    message = __truncate_message(message,nb_max_lines)
    if wx_available:
        dlg = wx.MessageDialog(parent, message,  title, wx.OK | wx.ICON_ASTERISK)
        if dlg.ShowModal() == wx.ID_OK:
            pass
        dlg.Destroy()
    else:
        print(title+": "+message)

def info_message_and_close(message,title="",parent=None):
    if wx_available:
        dlg = wx.MessageDialog(parent, message,  title, wx.OK | wx.ICON_ASTERISK)
        if dlg.ShowModal() == wx.ID_OK:
            pass
            parent.Destroy()
        dlg.Destroy()
    else:
        print("Info: "+message)

def warning_message(message,title="Warning",parent=None,nb_max_lines=30):
    message = __truncate_message(message,nb_max_lines)
    if wx_available:
        dlg = wx.MessageDialog(parent, message,  title, wx.OK | wx.ICON_WARNING)
        if dlg.ShowModal() == wx.ID_OK:
            pass
        dlg.Destroy()
    else:
        print(title+": "+message)

def __get_exception_message():
    msg = python_lacks.ascii_compliant("%s" % sys.exc_info()[1],best_ascii_approximation=True)
    return msg

def show_exception(title="Exception occurred",parent=None,with_traceback=True,thread_safe=True):
    if with_traceback:
        # get full exception traceback on the console
        traceback.print_exc()

    if thread_safe:
        wx.CallAfter(error_message,__get_exception_message(),title,parent)
    else:
        error_message(__get_exception_message(),title,parent)

def get_selected_items(list_widget,column_index=0):
    """
    return selected items (array of arrays) of a listctrl (may be extended to other list types)
"""
    rval = []
    item = -1
    while True:
        item = list_widget.GetNextSelected(item)
        #nb_cols = list_widget.GetColumnCount()
        if item==-1:
            break
        rval.append(list_widget.GetItem(item,column_index).GetText())

    return rval

def get_all_items(list_widget,column_index=0):
    """
    Return all items of a listctrl
    """
    rval = []
    count = list_widget.GetItemCount()
    for row in range(count):
        rval.append(list_widget.GetItem(row,column_index).GetText())
    return rval

def choice_message(choices,title="",default_choice=None,parent=None):
    """
    returns None on cancel
    returns choice position on OK
    """

    class ComboDialog(wx.Dialog):
        """"""

        #----------------------------------------------------------------------
        def __init__(self,parent,title,choices,default_choice):
            """Constructor"""
            wx.Dialog.__init__(self, parent=parent, title=title)

            okBtn = wx.Button(self, wx.ID_OK,pos=wx.Point(30, 60))
            cancelBtn = wx.Button(self, wx.ID_CANCEL,pos=wx.Point(150, 60))

            self.__combo = wx.Choice(choices=choices, id=500,
                  name=u'build_combo', parent=self,
                  pos=wx.Point(10, 10), size=wx.Size(280, 50), style=0)

            if default_choice!=None:
                self.__combo.SetSelection(default_choice)

            self.SetSize(wx.Size(300,120))
        def get_position(self):
            return self.__combo.GetSelection()

    cd = ComboDialog(parent,title,choices,default_choice)
    rc = cd.ShowModal()
    rval = None
    if rc==wx.ID_CANCEL:
        pass
    else:
        rval = cd.get_position()
        if rval==wx.NOT_FOUND:
            rval = None

    return rval


def yesno_message(message,title="",parent=None,icon=wx.ICON_INFORMATION,nb_max_lines=30):
    message = __truncate_message(message,nb_max_lines)
    dlg = wx.MessageDialog(parent, message,  title,
                            wx.YES | wx.NO | icon)
    rval = dlg.ShowModal() == wx.ID_YES

    dlg.Destroy()

    return rval

def set_text_value(widget,text):
    """
    set text value and show the end of the text in case widget is not wide enough
    """
    widget.SetValue(text)
    widget.SetInsertionPointEnd()

def select_file(title="Select a file",wildcard="*.*",parent=None,start_directory=None):
    """
    opens a windows-style requester to select a file
    title: requester title
    wildcard: filter pattern
    parent: parent widget
    start_directory: directory to open requester from
    """
    if wildcard=="*":
        # would not follow links with "*" (strange bug!!)
        wildcard="*.*" # also sees files without extensions => no need for "*"

    rval = None
    if start_directory==None:
        start_directory = os.curdir
    else:
        start_directory = eve.evaluate_environment_variables(start_directory)
    dialog = wx.FileDialog(parent, title, wildcard=wildcard, style=wx.FD_OPEN, defaultDir=start_directory)

    if dialog.ShowModal() == wx.ID_OK:
        rval = dialog.GetPath()
    return rval

def select_dir(title="",parent=None,start_directory=None,style=wx.DD_NEW_DIR_BUTTON,name=""):
    rval = None
    if start_directory == None:
        start_directory = os.curdir
    else:
        start_directory = eve.evaluate_environment_variables(start_directory)
    dialog = wx.DirDialog(parent=parent,message =title,defaultPath=start_directory,style = style,name=name)
    if dialog.ShowModal() ==wx.ID_OK:
        rval = dialog.GetPath()

    return rval

def input_box(message,title="", hidden=False, parent=None, default_value = ""):
    message = python_lacks.ascii_compliant(message)
    if hidden:
        dlg = wx.PasswordEntryDialog(parent, message, title, value=default_value)
    else:
        dlg = wx.TextEntryDialog(parent, message, title, defaultValue=default_value)

    ok = dlg.ShowModal() == wx.ID_OK
    rval = None
    if ok:
        rval = dlg.GetValue()

    dlg.Destroy()

    return rval


def set_busy_cursor(window):
    """
    sets cursor to hourglass in window
    """
    window.SetCursor,wx.StockCursor(wx.CURSOR_WAIT)

def set_arrow_cursor(window):
    """
    sets cursor to normal pointer in window
    """
    wx.CallAfter(window.SetCursor,wx.StockCursor(wx.CURSOR_ARROW))

def to_clipboard(text):
    """
    sets the string "text" in the shared clipboard
    """

    if not wx.TheClipboard.IsOpened():
        wx.TheClipboard.Open()
    do = wx.TextDataObject()
    do.SetText(u''+text)
    success = wx.TheClipboard.SetData(do)
    wx.TheClipboard.Close()

def from_clipboard():
    """
    gets the text contained in the clipboard
    """

    if not wx.TheClipboard.IsOpened():
        wx.TheClipboard.Open()
    do = wx.TextDataObject()
    text = do.GetText()
    success = wx.TheClipboard.GetData(do)
    wx.TheClipboard.Close()
    if success:
        text = do.GetText()
    else:
        text = ""
    return text

class Cursor:
    def __init__(self, frame):
        self.__start_operation = dict()
        self.__frame = frame
        self.__nb_wait = 0
        # We must create a lock object in order to have a thread safe cursor
        self.__cursor_lock = threading.Lock()

    def set_cursor(self,wait = True, operation = ""):
        self.__cursor_lock.acquire()

        if wait:
            if operation != "":
                self.__start_operation[operation] = time.time()

            if self.__nb_wait == 0:
                set_busy_cursor(self.__frame)

            self.__nb_wait += 1
        else:
            if operation != "":
                end_operation = time.time()
                print("Operation '%s' took %.02f seconds" % (operation,end_operation - self.__start_operation[operation]))

            self.__nb_wait -= 1

            if self.__nb_wait == 0:
                set_arrow_cursor(self.__frame)

        self.__cursor_lock.release()

#Class to print message in the console for debug
class Logger:
    """
    Level :
        1 for critical
        2 for error
        3 for warning
        4 for info
        5 for debug
    """
    def __init__(self,level=1,application="",tab="", date=True, filename=""):
        #To generate a unique ref for the logger
        import random
        number = random.randint(0,100000)

        #Format of the logger
        format=tab
        if date :
            format += '%(asctime)s -'
        if application == "":
            format += '%(name)s - %(levelname)s - %(message)s'
        else:
            format += application + ' %(levelname)s - %(message)s'

        self.__logger = logging.getLogger(str(number))

        #Level of logger
        if level == 1 :
            self.__logger.setLevel(logging.CRITICAL)
        elif level == 2:
            self.__logger.setLevel(logging.ERROR)
        elif level == 3 :
            self.__logger.setLevel(logging.WARNING)
        elif level == 4 :
            self.__logger.setLevel(logging.INFO)
        elif level == 5:
            self.__logger.setLevel(logging.DEBUG)
        else:
            self.__logger.setLevel(logging.CRITICAL)

        #Format of the logger
        formatter = logging.Formatter(format)
        if filename != "":
            logfile = logging.FileHandler(filename)
            logfile.setFormatter(formatter)
            self.__logger.addHandler(logfile)
        else:
            stream = logging.StreamHandler()
            stream.setFormatter(formatter)
            self.__logger.addHandler(stream)

    def get_logger(self):
        return self.__logger

    #Methods for completion
    def debug(self,message):
        self.__logger.debug(message)

    def info(self,message):
        self.__logger.info(message)

    def warning(self,message):
        self.__logger.warning(message)

    def error(self,message):
        self.__logger.error(message)

    def critical(self,message):
        self.__logger.critical(message)

import threading
from functools import wraps

#Class to create a frame to follow execution
def __load_frame(parent):

    def create(parent):
        return Loader(parent)

    [wxID_LOADER, wxID_LOADER_GAUGE, wxID_LOADER_PANEL, wxID_LOADER_STATE] = [wx.NewId() for _init_ctrls in range(4)]

    class Loader(wx.Frame):
        def _init_ctrls(self, prnt):
            # generated method, don't edit
            wx.Frame.__init__(self, id=wxID_LOADER, name=u'Loader', parent=prnt,
                  pos=wx.Point(470, 348), size=wx.Size(415, 94), style=wx.DEFAULT_FRAME_STYLE, title=u'Loading...')
            self.SetClientSize(wx.Size(407, 67))
            self.SetHelpText(u'')
            self.SetToolTipString(u'Loading')

            self.panel = wx.Panel(id=wxID_LOADER_PANEL, name='panel', parent=self,
                  pos=wx.Point(0, 0), size=wx.Size(407, 67), style=wx.TAB_TRAVERSAL)

            self.gauge = wx.Gauge(id=wxID_LOADER_GAUGE, name='gauge',
                  parent=self.panel, pos=wx.Point(16, 32), range=100,
                  size=wx.Size(376, 16), style=wx.GA_HORIZONTAL)

            self.state = wx.StaticText(id=wxID_LOADER_STATE, label=u'',
                  name=u'state', parent=self.panel, pos=wx.Point(16, 8), size=wx.Size(0, 13), style=0)

        def __init__(self, parent):
            self._init_ctrls(parent)

        def set_state(self, state_value):
            self.state.SetSize(wx.Size(400,13))
            self.state.SetLabel(state_value)

        def set_percent(self, percent):
            value = percent*0.01*self.gauge.Range
            self.gauge.SetValue(value)

    l = create(parent)
    return l

# Each thread can run one to X progress bar
__thread_pbars = {}

def progressing(f):

    @wraps(f)
    def f_progressing(*args, **kwargs):
        if len(args) > 0 and args[0].__class__.__dict__['__module__'].startswith("wx._windows"):
            # Decorator is set to a Wx element method
            # Use is as parent
            parent = args[0]
        else:
            parent = None

        # Create progress bar
        loader_bar = __load_frame(parent)
        current_thread = threading.currentThread()
        if current_thread not in __thread_pbars:
            __thread_pbars[current_thread] = []

        __thread_pbars[current_thread].append(loader_bar)

        loader_bar.Show()

        try:
            rval = f(*args, **kwargs)
        finally:
            # Destroy progress bar
            loader_bar.set_state("Finished...")
            loader_bar.set_percent(100)
            loader_bar.Destroy()

        __thread_pbars[current_thread].remove(loader_bar)

        return rval

    return f_progressing  # true decorator

def get_progress_bar():
    current_thread = threading.currentThread()

    if current_thread in __thread_pbars and \
        len(__thread_pbars[current_thread]) > 0:
            # Return last instantiation of progress bar
            return __thread_pbars[current_thread][-1]
    else:
        raise Exception("No progress bar running for this instance.")