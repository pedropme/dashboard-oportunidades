@echo off
echo ============================================
echo  Compilando Atualizar Dashboard.exe
echo ============================================
echo.

pip install pyinstaller >nul 2>&1

pyinstaller --onefile --windowed --name "Atualizar Dashboard" --clean atualizar.py

echo.
if exist "dist\Atualizar Dashboard.exe" (
    echo  Pronto! Copiando o .exe para a pasta raiz...
    copy /Y "dist\Atualizar Dashboard.exe" "Atualizar Dashboard.exe" >nul
    echo  Arquivo criado: Atualizar Dashboard.exe
    echo.
    echo  Pode apagar as pastas dist\ e build\ se quiser.
) else (
    echo  Algo deu errado. Verifique as mensagens acima.
)

echo.
pause
