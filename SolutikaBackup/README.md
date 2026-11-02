# Solutika Backup

Ferramenta do técnico para **backup**, **restauração** e **ficha de atendimento (PDF)**.

## Seções
1. **Backup de arquivos**: salva o perfil do usuário (arquivos, AppData compactado, navegadores, drivers e
   inventário de softwares/impressoras) com validação no final.
2. **Restauração**: escolhe o backup e o usuário de destino e devolve arquivos, AppData e drivers.
3. **Ficha do técnico**: formulário com checklists (serviços, peças trocadas, verificações) e observações.
   O texto do que foi feito no backup e na restauração é gerado automaticamente. Gera um PDF para anexar ao chamado.

## Gerar o executável (Windows)
1. Instale o Python 3.10+ (python.org) marcando **Add python.exe to PATH**.
2. Dê duplo clique em `build.bat` (precisa de internet na primeira vez).
3. O arquivo final fica em `dist\SolutikaBackup.exe` (um único arquivo, sem console).

`build.bat admin` gera uma versão que **sempre** pede administrador ao abrir.
Sem esse parâmetro, o programa abre normal e tem o botão **Reabrir como administrador** na barra lateral.

Para testar sem gerar o .exe: `executar.bat` (ou `python main.py`).

## Dicas
- Execute o .exe de um disco local (Desktop/pendrive). O Windows elevado não enxerga unidades de rede mapeadas.
- Erros inesperados são gravados em `%APPDATA%\SolutikaBackup\erro.log`.
- Cada backup grava `_meta\eventos.json`; é daí que a ficha tira a descrição automática (também ao restaurar).

## Novidades da versão 2.1
- **Backup:** o AppData tem três modos (Completo, Essencial, Não levar) e os navegadores têm escolha própria, por navegador.
- **Restauração:** o botão "Ver lista de softwares" abre uma janela com busca, filtros, marcação do que foi reinstalado,
  lista de impressoras (com o tipo de conexão) e exportação para CSV ou para a ficha.
- **Ficha:** serviços e peças com situação (Realizado/Trocada, Não necessário, Pendente). As verificações finais foram removidas.
- **Tema:** botão sol/lua no canto superior direito alterna entre o tema claro e o escuro (a escolha fica salva).
