"""Copy only built portal files to Vercel's root public directory."""

import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "frontend/dist"
target = root / "public"
if target.is_symlink() or not target.resolve().is_relative_to(root):
    raise SystemExit("Diretório público fora do workspace")
if not (source / "index.html").is_file():
    raise SystemExit("Execute o build frontend antes de preparar os arquivos estáticos")
for path in source.rglob("*"):
    if path.is_file():
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise SystemExit("Arquivo de build fora do diretório esperado")
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
print("Portal estático preparado em public/; nenhum deploy executado")
