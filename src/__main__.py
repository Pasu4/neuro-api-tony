import wx

from .controller import HumanController

if __name__ == '__main__':
    app = wx.App()
    controller = HumanController(app)
    controller.run()