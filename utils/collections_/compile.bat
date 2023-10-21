@ECHO OFF

set shouldPause=true
set shouldExit=false
set shouldCleanFirst=false

for %%a in (%*) do (
    if "%%a"=="/noPause" set shouldPause=false
    if "%%a"=="/exit" set shouldExit=true
    if "%%a"=="/clean" set shouldCleanFirst=true
)

if %shouldCleanFirst%==true rmdir build /q /s
python setup.py build_ext --inplace

if %shouldPause%==true pause
if %shouldExit%==true exit
