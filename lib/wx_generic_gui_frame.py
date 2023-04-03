import wx,wx.lib.buttons
import sys,os,fnmatch,re
import traceback,pickle

# if available, import network_specifics to change profile directory
try:
    import network_specifics
    user_home_directory = network_specifics.misc_config.user_home_directory
except:
    user_home_directory = os.getenv("USERPROFILE")

try:
    unicode
except NameError:
    # python 2/3 compatibility: unicode is gone from Python 3, make it == str
    unicode = str

# custom TUP modules

import eve      # environment variable evaluator
import passcr   # password cipher
import wx_utils # wx widget utility functions


[wxID_FIND, wxID_FINDCANCELBUTTON, wxID_FINDCOMMITBUTTON,
 wxID_FINDDRIVE_COMBO, wxID_FINDPANEL1,
 wxID_FINDRESTART_BUTTON,
] = [wx.NewId() for _init_ctrls in range(6)]


class GenericApp(wx.App):
    def __init__(self):
        wx.App.__init__(self,redirect=False)
        if False:
            # never reached, but completion in PyScripter works
            self.__frame = GenericGuiFrame()
        self.__frame = None

    def _init(self):
        raise Exception("Redefine _init method")

    def get_process_comm_object(self):
        return self.__frame.get_process_comm_object()

    def OnInit(self):
        try:
            self._init()
        except:
            wx_utils.show_exception(thread_safe=False)
            return False

        self.__frame.Show()
        self.SetTopWindow(self.__frame)
        self.MainLoop()
        return True

    def get_frame(self):
        return self.__frame

    def register_frame(self,frame):
        if False:
            # never reached, but completion in PyScripter works
            frame = GenericGuiFrame()

        self.__frame = frame
        return frame

    def set_title(self,title):
        self.__frame.SetTitle(title)

    def exit(self):
        self.Destroy()
        sys.exit(0)

class GenericGuiFrame(wx.Frame):
    # remove "library.zip" if embedded in py2exe
    __MODULE_FILE = __file__.replace(os.sep+"library.zip","")
    __PROGRAM_DIR = os.path.dirname(__MODULE_FILE)

    def get_process_comm_object(self):
        return self.__process_comm

    def __is_disk_related_field(self,k):
        klow = k.lower()
        return any(x in klow for x in ["path","file","directory"])

    def __init__(self, parent, params, callback, width=500, key_list = None, persist_as = None, label_width = 120, combo_list_limit = 100, save_passwords = False, widget_height=25):

        self.__callback = callback
        self.__fields = dict()  # param name => widget & type
        self.__widgets = dict() # widget => param name & type
        self.__combo_list_limit = combo_list_limit
        self.__persist_as = re.sub("[\\/:]","_",persist_as)
        self.__save_passwords = save_passwords

        default_values = dict()

        if self.__persist_as:
            self.__config_file = os.path.join(user_home_directory,persist_as+".ini")
            if os.path.exists(self.__config_file):
                try:
                    # read params from table using pickle
                    with open(self.__config_file,"rb") as f:
                        default_values = pickle.load(f)
                except:
                    # in case .ini file is corrupt
                    default_values = dict()

                # update input dictionary

                for k,v in params.items():
                    if k in default_values:
                        # already set
                        pass
                    else:
                        # new parameter (tool update)
                        default_values[k] = v

                pk = list(default_values.keys())
                for k in pk:
                    if k in params:
                        pass
                    else:
                        # remove old parameter to avoid accumulation
                        default_values.pop(k)

            for k in params:
                if k.lower().find("password")==-1:
                    pass
                else:
                    if params[k]!="":
                        params[k] = passcr.decipher(params[k])

        wx.Frame.__init__(self, id=wxID_FIND, name=u'ViewUpdater',
              parent=parent, pos=wx.Point(585, 277), size=wx.Size(613, width),
              style=wx.DEFAULT_FRAME_STYLE, title=u'View Updater')
        self.SetHelpText(u'')

        if key_list == None:
            key_list = sorted(params.keys())


        self.__panel1 = wx.Panel(id=wxID_FINDPANEL1, name='panel1',
              parent=self, pos=wx.Point(0, 0), size=wx.Size(605, width),
              style=wx.TAB_TRAVERSAL)

        current_y = widget_height//2
        field_x = label_width
        field_width = width-field_x
        for k in key_list:
            p = params[k]
            default_value = None
            if k in default_values:
                default_value = default_values[k]
            pos = wx.Point(field_x, current_y)
            text = wx.StaticText(id=wx.NewId(),
                  label=k, name='staticText1', parent=self.__panel1,
                  pos=wx.Point(10, current_y), size=wx.Size(field_x-10, widget_height), style=0)
            if isinstance(p,bool):
                field = wx.CheckBox(id=wx.NewId(), name=u'combo',
                parent=self.__panel1, pos=pos, size=wx.Size(field_width, widget_height),
                style=0)
                if default_value==None:
                    field.SetValue(p)
                else:
                    field.SetValue(default_value)

            elif isinstance(p,int):
                field = wx.TextCtrl(id=wx.NewId(),
                      name='staticText1', parent=self.__panel1,
                      pos=pos, size=wx.Size(field_width, widget_height), style=0)
                if default_value==None:
                    field.SetValue(str(p))
                else:
                    field.SetValue(str(default_value))

                field.SetToolTip(wx.ToolTip(u'enter an integer value'))
            elif isinstance(p,float):
                field = wx.TextCtrl(id=wx.NewId(),
                      name='staticText1', parent=self.__panel1,
                      pos=pos, size=wx.Size(field_width, widget_height), style=0)
                if default_value==None:
                    field.SetValue(str(p))
                else:
                    field.SetValue(str(default_value))
                field.SetToolTip(wx.ToolTip(u'enter a float value'))
            elif isinstance(p,str) or isinstance(p,unicode):
                klow = k.lower()
                sz = field_width
                file_selection_widget = False
                if self.__is_disk_related_field(k):
                    file_selection_widget = True
                    sz -= 21

                if klow.find('password')==-1:
                    style = 0
                else:
                    style = wx.TE_PASSWORD

                field = wx.TextCtrl(id=wx.NewId(),
                      name='staticText1', parent=self.__panel1,
                      pos=pos, size=wx.Size(sz, widget_height), style=style)

                if default_value==None:
                    field.SetValue(p)
                else:
                    field.SetValue(default_value)
                if file_selection_widget:
                    field.SetToolTip(wx.ToolTip(u'enter/drop a filepath'))
                    wx_utils.enable_filename_drop(field)
                    picture = wx.Bitmap(os.path.join(self.__PROGRAM_DIR,'windows_explorer.png'))

                    explorer_id = wx.NewId()
                    explorer_button = wx.lib.buttons.GenBitmapButton(bitmap=picture, id=explorer_id,
                          name=u'windows_explorer_button', parent=self.__panel1,
                          pos=wx.Point(field_x+sz, current_y), size=wx.Size(21, 21), style=0)

                    explorer_button.associated_textfield = field
                    explorer_button.directory_selection =  klow.find("directory")!=-1
                    if explorer_button.directory_selection:
                        explorer_button.SetToolTip(wx.ToolTip(u"select directory"))
                    else:
                        explorer_button.SetToolTip(wx.ToolTip(u"select file"))

                    explorer_button.Bind(wx.EVT_BUTTON,
                          self.__on_select_file,
                          id=explorer_id)
                    if default_value==None:
                        field.SetValue(p)
                    else:
                        field.SetValue(default_value)

                else:
                    field.SetToolTip(wx.ToolTip(u'enter a string value'))
            elif isinstance(p,list):
                ch = list()
                use_external_window = len(p)>self.__combo_list_limit

                # we compose the list without leading "_" and
                # compute default value AND default position so we can handle
                # both string selection and index selection (according to selection method)
                default_position = -1
                for i,item in enumerate(p):
                    sitem = item.strip("_")
                    ch.append(sitem)
                    if default_value == None:
                        if item.startswith("_"):
                            default_position = i
                            default_value = sitem
                    else:
                        # there is a default value
                        if default_value == sitem:
                            default_position = i

                if use_external_window:
                    sz = field_width - 21

                    nid = wx.NewId()
                    field = wx.TextCtrl(id=nid,
                                          name='staticText1', parent=self.__panel1,
                                          pos=pos, size=wx.Size(sz, 20), style=0)
                    picture = wx.Bitmap(os.path.join(self.__PROGRAM_DIR,'search.png'))
                    field.SetEditable(False)

                    combo_popup_id = wx.NewId()
                    combo_popup_button = wx.lib.buttons.GenBitmapButton(bitmap=picture, id=combo_popup_id,
                          name=u'', parent=self.__panel1,
                          pos=wx.Point(field_x+sz, current_y), size=wx.Size(21, 21), style=0)

                    combo_popup_button.associated_textfield = field
                    combo_popup_button.associated_items = p
                    combo_popup_button.Bind(wx.EVT_BUTTON,
                          self.__on_select_item,
                          id=combo_popup_id)
                    if default_value!=None:
                        field.SetValue(default_value)

                else:
                    field = wx.Choice(choices=ch,id=wx.NewId(), name=u'combo',
                    parent=self.__panel1, pos=pos, size=wx.Size(field_width, 20),
                    style=0)
                    if default_position>=0:
                        field.SetSelection(default_position)


            self.__fields[k] = [field,p]
            self.__widgets[field.GetId()] = [k,p]
            current_y += widget_height + widget_height//2


        self.__commit_button = wx.Button(id=wxID_FINDCOMMITBUTTON,
              label=u'-', name=u'CommitButton', parent=self.__panel1,
              pos=wx.Point(width//2-80, current_y), size=wx.Size(75, 23), style=0)
        self.__commit_button_runs()

        self.__cancel_button = wx.Button(id=wxID_FINDCANCELBUTTON,
              label=u'Quit', name=u'CancelButton', parent=self.__panel1,
              pos=wx.Point(width//2+5, current_y), size=wx.Size(75, 23), style=0)
        self.__cancel_button.SetToolTip(wx.ToolTip(u'Quit'))
        self.__cancel_button.Bind(wx.EVT_BUTTON, self.__on_cancel_button,
              id=wxID_FINDCANCELBUTTON)

        self.SetClientSize(wx.Size(width+10, current_y+50))

    def set_modify_callback(self,k,callback):
        (w,p) = self.__fields[k]
        wid = w.GetId()
        w.callback = callback
        etype = None
        if isinstance(w,wx.TextCtrl):
            etype = wx.EVT_TEXT
        elif isinstance(w,wx.Choice):
            etype = wx.EVT_CHOICE
        elif isinstance(w,wx.CheckBox):
            etype = wx.EVT_CHECKBOX
        if etype != None:
            w.Bind(etype, self.__on_modified,id=wid)

    def __on_modified(self,event):
        event.Skip()
        w = event.GetEventObject()

        w.callback(w,self.__widgets[w.GetId()][0])

    def enable(self,k,state):
        self.get_widget(k).Enable(state)

    def set_tooltip_string(self,k,tooltip):
        self.get_widget(k).SetToolTip(wx.ToolTip(tooltip))

    def get_widget(self,k):
        return self.__fields[k][0]

    def __error(self,msg):
        raise Exception(msg)

    def __on_select_item(self, event):
        event.Skip()
        textfield = event.GetEventObject().associated_textfield
        items = event.GetEventObject().associated_items

        w = wx_utils.BigListChoice(parent=self.__panel1,title="",items=items)
        w.ShowModal()
        item = w.get_selected_item()
        if item != None :
            textfield.ChangeValue(item)

    def __on_select_file(self, event):
        event.Skip()
        textfield = event.GetEventObject().associated_textfield
        tv = textfield.GetValue()
        start_directory = None
        if event.GetEventObject().directory_selection:
            if tv != "":
                start_directory = tv
            f = wx_utils.select_dir(parent=self,start_directory=start_directory)
        else:
            if tv != "":
                start_directory = os.path.dirname(tv)
            f = wx_utils.select_file(parent=self,start_directory=start_directory)
        if f != None:
            textfield.SetValue(f)

    @staticmethod
    def __create_directory(dirpath):
        """
        create dir, but do not crash if already exists
        """

        if os.path.isdir(dirpath):
            pass
        else:
            os.makedirs(dirpath)


    def get_value(self,key):
        r = None
        field = self.__fields[key][0]
        p = self.__fields[key][1]
        if isinstance(p,bool):
            r = field.GetValue()
        elif isinstance(p,int):
            r = int(field.GetValue())
        elif isinstance(p,float):
            r = float(field.GetValue())
        elif isinstance(p,str):
            r = field.GetValue()
        elif isinstance(p,list):
            if isinstance(field,wx.TextCtrl):
                r = field.GetValue()
            else:
                r = field.GetStringSelection()

        return r

    def __callback_wrapper(self, args):
        c = wx_utils.Cursor(self)
        c.set_cursor()
        try:
            self.__callback(args)
        except SystemExit:
            sys.exit(0)
        except:
            #e=traceback.format_exc()
            self.__show_exception()

        finally:
            c = wx_utils.Cursor(self)
            c.set_cursor(wait = False)

    def __on_commit_button(self, event):
        event.Skip()
        current_field = None


        try:
            params = dict()
            for k,v in self.__fields.items():
                current_field = k
                is_password = k.lower().find('password')!=-1
                r = self.get_value(k)
                if r != None:
                    if is_password:
                        if self.__save_passwords:
                            # if must save password field, encrypt it
                            r = passcr.cipher(r)
                    else:
                        # standard field
                        pass
                    params[k] = r

            current_field = None
            if self.__persist_as != None:
                self.__create_directory(os.path.dirname(self.__config_file))
                f=open(self.__config_file,"wb")
                pickle.dump(params,f)
                f.close()

            # evaluate env. variable for file/directory parameters AFTER having dumped the variables
            for k,v in params.items():
                if isinstance(self.__fields[k][1],str) and self.__is_disk_related_field(k):
                    params[k] = eve.evaluate_environment_variables(v)

        except:
            e=traceback.format_exc()
            if current_field:
                self.__show_exception("Parsing error for '"+current_field+"'")
            else:
                self.__show_exception()

        # then call the user callback function
        else:
            self.__callback_wrapper(params)



    def __commit_button_runs(self):
        self.__commit_button.SetLabel(u'Run')
        self.__commit_button.SetToolTip(wx.ToolTip(u'Run the tool'))
        self.__commit_button.Bind(wx.EVT_BUTTON, self.__on_commit_button,
              id=wxID_FINDCOMMITBUTTON)

    def __show_exception(self,title="Exception occurred"):
        #error_report.ErrorReport()
        wx_utils.show_exception(title=title,parent=self)

    def on_quit(self):
        pass

    def __on_cancel_button(self, event):
        event.Skip()
        self.on_quit()
        self.Close()