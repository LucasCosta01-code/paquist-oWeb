@echo off
echo ===================================================
echo     PREPARANDO ENVIO PARA O GITHUB / RAILWAY
echo ===================================================
echo.
echo [1/3] Adicionando arquivos corrigidos...
git add .
echo.
echo [2/3] Criando pacote de correcao...
git commit -m "Correcao pacote helmet e deploy"
echo.
echo [3/3] Enviando para o GitHub (Aguarde)...
git push
echo.
echo ===================================================
echo PRONTINHO! Os arquivos foram enviados com sucesso!
echo Agora basta aguardar o Deploy novo na Railway ficar VERDE.
echo ===================================================
pause
