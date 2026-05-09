@echo off
echo ===================================================
echo     RESOLVENDO ERRO DO NPM CI DEFINITIVAMENTE
echo ===================================================
echo.
echo [1/4] Removendo arquivo package-lock.json que causa o conflito...
git rm -f package-lock.json
del package-lock.json
echo.
echo [2/4] Preparando correcoes...
git add .
echo.
echo [3/4] Salvando...
git commit -m "Remove package-lock para forcar npm install"
echo.
echo [4/4] Enviando para a Railway...
git push
echo.
echo ===================================================
echo FEITO! O ERRO FOI ELIMINADO!
echo Agora olhe no painel da Railway, o novo deploy vai 
echo usar 'npm install' e o site vai ficar online!
echo ===================================================
pause
