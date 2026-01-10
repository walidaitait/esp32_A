@echo off
echo ===============================
echo   Aggiornamento GitHub ESP32A
echo ===============================

REM Controllo che la cartella sia un repository git
if not exist ".git" (
    echo ERRORE: questa cartella NON e' un repository Git.
    echo Esegui prima: git init
    pause
    exit /b
)

REM Mostra lo stato attuale
echo.
echo Stato dei file:
git status

echo.
echo Aggiungo i file...
git add .

REM Commit automatico con data e ora
set DATETIME=%date% %time%
git commit -m "Auto update %DATETIME%" >nul 2>&1

REM Push su GitHub
echo.
echo Invio aggiornamenti a GitHub...
git push -u origin main

echo.
echo Operazione completata.
pause
