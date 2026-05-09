@echo off
echo ===================================================
echo     CORRIGINDO ERRO DE SEGURANCA DO GITHUB
echo ===================================================
echo.
echo [1/3] Removendo arquivo com senhas do ultimo pacote...
git reset --soft HEAD~1
git rm --cached .env
echo.
echo [2/3] Criando pacote seguro...
git add .
git commit -m "Deploy seguro do novo sistema"
echo.
echo [3/3] Enviando para o GitHub/Railway...
git push
echo.
echo ===================================================
echo ERRO CORRIGIDO COM SUCESSO!
echo ===================================================
pause
