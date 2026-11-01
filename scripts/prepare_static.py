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
# public/assets is generated exclusively from Vite; drop obsolete hashed outputs.
asset_target = target / "assets"
if asset_target.exists():
    if asset_target.is_symlink() or not asset_target.resolve().is_relative_to(target.resolve()):
        raise SystemExit("Diretório de assets fora do destino esperado")
    for previous in asset_target.rglob("*"):
        if previous.is_file():
            if previous.is_symlink() or not previous.resolve().is_relative_to(target.resolve()):
                raise SystemExit("Asset fora do destino esperado")
            if not (source / previous.relative_to(target)).is_file():
                previous.unlink()
for path in source.rglob("*"):
    if path.is_file():
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise SystemExit("Arquivo de build fora do diretório esperado")
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
print("Portal estático preparado em public/; nenhum deploy executado")
