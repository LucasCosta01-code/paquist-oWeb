@echo off
echo ===================================================
echo     ATUALIZANDO SITE E BOTS NA RAILWAY
echo ===================================================
echo.
echo [1/2] Criando pacote do Dockerfile...
git add .
git commit -m "Deploy do Dockerfile"
echo.
echo [2/2] Forcando envio para o GitHub/Railway...
git push -f origin main
echo.
echo ===================================================
echo DEPLOY CONCLUIDO COM SUCESSO!
echo ===================================================
pause
