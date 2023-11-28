
# Cat GUI
![GitHub](https://img.shields.io/github/license/JoachimCoenen/cat-gui)
![GitHub repo size](https://img.shields.io/github/repo-size/JoachimCoenen/cat-gui?color=0072FF)
![Lines of code](https://img.shields.io/tokei/lines/github/JoachimCoenen/cat-gui?color=0072FF)
[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FJoachimCoenen%2Fcat-gui&count_bg=%230072FF&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com)

An [imgui](https://github.com/ocornut/imgui) style gui library for python using Qt5 as its backend.

Used by [Datapack Editor](https://github.com/JoachimCoenen/Datapack-Editor).

### Example
```
    class ExampleMainWindow(CatFramelessWindowMixin, QDialog):
    	def OnGUI(self, gui: AutoGUI):
            with gui.hLayout():
        		name = gui.textField(None, label="name")
                if gui.button(f"greet {name}"):
                    gui.showInformationDialog(f"Hello {name}!", "How are you?")
```


[NewIssue_LINK]:                 https://github.com/JoachimCoenen/cat-gui/issues/new  "New issue"
