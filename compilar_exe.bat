@echo off
echo ============================================
echo  Compilando Atualizar Dashboard.exe
echo ============================================
echo.

echo Instalando PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo.
    echo ERRO: Python nao encontrado ou pip falhou.
    echo Certifique-se de que o Python esta instalado e no PATH.
    pause
    exit /b 1
)

echo.
echo Compilando...
python -m PyInstaller --onefile --windowed --name "Atualizar Dashboard" --clean atualizar.py
if errorlevel 1 (
    echo.
    echo ERRO: Compilacao falhou. Veja as mensagens acima.
    pause
    exit /b 1
)

echo.
if exist "dist\Atualizar Dashboard.exe" (
    echo Copiando o .exe para a pasta raiz...
    copy /Y "dist\Atualizar Dashboard.exe" "Atualizar Dashboard.exe"
    echo.
    echo  Pronto! Arquivo criado: "Atualizar Dashboard.exe"
    echo  Pode apagar as pastas dist\ e build\ se quiser.
) else (
    echo ERRO: .exe nao foi gerado.
)

echo.
pause
