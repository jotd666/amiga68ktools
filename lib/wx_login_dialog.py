#Boa:Dialog:LoginDialog

import wx
import os

def create(parent, title="Login", login=os.getenv("USERNAME"), password=""):
    return LoginDialog(parent, title, login, password)

[wxID_LOGINDIALOG,
 wxID_LOGINDIALOGLOGIN, wxID_LOGINDIALOGOK,
 wxID_LOGINDIALOGPASSWORD, wxID_LOGINDIALOGSTATICTEXT1,
 wxID_LOGINDIALOGSTATICTEXT2,
] = [wx.NewId() for _init_ctrls in range(6)]

class CancelLoginException(Exception):
    pass

class LoginDialog(wx.Dialog):
    def _init_ctrls(self, prnt, title):
        # generated method, don't edit
        wx.Dialog.__init__(self, id=wxID_LOGINDIALOG,
              name=u'LoginDialog', parent=prnt, pos=wx.Point(432, 315),
              size=wx.Size(299, 143), style=wx.DEFAULT_DIALOG_STYLE,
              title=title)
        self.SetClientSize(wx.Size(220, 116))
        self.Enable(True)
        self.SetBackgroundColour(wx.Colour(211, 211, 211))
        self.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.NORMAL, False,
              u'Tahoma'))

        self.ok = wx.Button(id=wxID_LOGINDIALOGOK, label=u'OK',
              name=u'ok', parent=self, pos=wx.Point(70, 88), size=wx.Size(75,
              23), style=0)
        self.ok.SetDefault()
        self.ok.Bind(wx.EVT_BUTTON, self.__on_ok_button,
              id=wxID_LOGINDIALOGOK)

        self.login = wx.TextCtrl(id=wxID_LOGINDIALOGLOGIN,
              name=u'login', parent=self, pos=wx.Point(72, 16),
              size=wx.Size(100, 21), style=0, value=u'')

        self.password = wx.TextCtrl(id=wxID_LOGINDIALOGPASSWORD,
              name=u'password', parent=self, pos=wx.Point(72, 48),
              size=wx.Size(100, 21), style=wx.TE_PASSWORD, value=u'')

        self.staticText1 = wx.StaticText(id=wxID_LOGINDIALOGSTATICTEXT1,
              label=u'Login :', name='staticText1', parent=self,
              pos=wx.Point(30, 16), size=wx.Size(32, 13), style=0)

        self.staticText2 = wx.StaticText(id=wxID_LOGINDIALOGSTATICTEXT2,
              label=u'Password :', name='staticText2', parent=self,
              pos=wx.Point(8, 48), size=wx.Size(53, 13), style=0)

    def __init__(self, parent, title, login, password):
        self._init_ctrls(parent, title)
        self.login.SetValue(login)
        self.password.SetValue(password)

        self.password.SetFocus()

    def __on_ok_button(self, event):
        event.Skip()
        self.EndModal(wx.ID_OK)
        self.Destroy() # Keep this line !

    def get_login(self):
        return self.login.GetValue()

    def get_password(self):
        return self.password.GetValue()