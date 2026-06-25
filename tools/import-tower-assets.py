from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path("/Users/nckzvth/Downloads")
TMP = Path("/tmp/leafbound-tower-assets")
PYTHON = "python3"

RUNTIME = ROOT / "assets" / "runtime"
PREVIEWS = ROOT / "assets" / "previews"
BOSSES = ROOT / "assets" / "bosses"
FX = ROOT / "assets" / "fx"
DARK_FOREST = ROOT / "assets" / "backgrounds" / "darkforest"
TOWER = ROOT / "assets" / "backgrounds" / "tower"
HIGH_FOREST = ROOT / "assets" / "backgrounds" / "highforest"
PRE_TOWER = ROOT / "assets" / "backgrounds" / "pretower"
UI = ROOT / "assets" / "ui"

for directory in (RUNTIME, PREVIEWS, BOSSES, FX, DARK_FOREST, TOWER, HIGH_FOREST, PRE_TOWER, UI, TMP):
    directory.mkdir(parents=True, exist_ok=True)


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def slice_png(src: Path, dst: Path, box: tuple[int, int, int, int]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGBA").crop(box).save(dst)


def unpack(rar: str) -> None:
    subprocess.run(["bsdtar", "-xf", str(DOWNLOADS / rar), "-C", str(TMP)], check=True)


def normalized_cell(
    source: Image.Image,
    box: tuple[int, int, int, int],
    union_bounds: tuple[int, int, int, int],
    out_size: int = 64,
) -> Image.Image:
    # Crop every frame in an animation row with the same bounds. This preserves
    # intended foot/body offsets inside the source cells instead of re-centering
    # each frame independently, which causes visible drifting in-game.
    cell = source.crop(box).convert("RGBA")
    sprite = cell.crop(union_bounds)
    frame = Image.new("RGBA", (out_size, out_size))
    x = (out_size - sprite.width) // 2
    y = out_size - 5 - sprite.height
    frame.alpha_composite(sprite, (x, y))
    return frame


def save_rows(
    source_path: Path,
    destination: Path,
    frame_width: int,
    frame_height: int,
    rows: list[list[tuple[int, int]]],
    labels: list[str],
) -> None:
    source = Image.open(source_path).convert("RGBA")
    sheet = Image.new("RGBA", (64 * max(len(row) for row in rows), 64 * len(rows)))
    preview = Image.new("RGBA", (64 * 4 * max(len(row) for row in rows), 64 * 4 * len(rows) + 28), (18, 20, 28, 255))
    draw = ImageDraw.Draw(preview)
    for row_index, row in enumerate(rows):
        bounds = []
        for src_row, src_col in row:
            cell = source.crop(
                (
                    src_col * frame_width,
                    src_row * frame_height,
                    (src_col + 1) * frame_width,
                    (src_row + 1) * frame_height,
                )
            ).convert("RGBA")
            cell_bounds = cell.getchannel("A").getbbox()
            if cell_bounds:
                bounds.append(cell_bounds)
        if bounds:
            union_bounds = (
                min(b[0] for b in bounds),
                min(b[1] for b in bounds),
                max(b[2] for b in bounds),
                max(b[3] for b in bounds),
            )
        else:
            union_bounds = (0, 0, frame_width, frame_height)
        for col_index, (src_row, src_col) in enumerate(row):
            frame = normalized_cell(
                source,
                (
                    src_col * frame_width,
                    src_row * frame_height,
                    (src_col + 1) * frame_width,
                    (src_row + 1) * frame_height,
                ),
                union_bounds,
            )
            sheet.alpha_composite(frame, (col_index * 64, row_index * 64))
            preview.alpha_composite(
                frame.resize((256, 256), Image.Resampling.NEAREST),
                (col_index * 256, row_index * 256),
            )
        draw.text((4, row_index * 256 + 4), labels[row_index], fill=(255, 230, 150, 255))
    sheet.save(destination)
    preview.save(PREVIEWS / f"{destination.stem}.png")


def main() -> None:
    for rar in (
        "Dark VFX 01 - 02.rar",
        "Thunder Effect 01.rar",
        "Thunder Effect 02.rar",
        "Earth Effect 01.rar",
        "Wind Effect 02.rar",
        "Magical Animation Effects.rar",
        "Fantasy Skeleton Enemies.rar",
    ):
        unpack(rar)

    # Environment sources.
    copy(DOWNLOADS / "DarkForest1" / "main_background.png", DARK_FOREST / "main-background.png")
    for name in ("bgrd_tree1.png", "bgrd_tree2.png", "bgrd_tree3.png", "bgrd_tree4.png", "bgrd_tree5.png"):
        copy(DOWNLOADS / "DarkForest1" / name, DARK_FOREST / name.replace("_", "-"))
    for name in ("env_ground.png", "env_rock.png", "castle_env.png", "decorative_obj.png", "wood_env.png"):
        copy(DOWNLOADS / "DarkForest1" / name, DARK_FOREST / name.replace("_", "-"))
    copy(DOWNLOADS / "PixelPlatformerSet2v" / "main_lev_buildA.png", TOWER / "main-level-build-a.png")
    copy(DOWNLOADS / "PixelPlatformerSet2v" / "main_lev_buildB.png", TOWER / "main-level-build-b.png")
    for index in range(1, 7):
        copy(DOWNLOADS / "PixelPlatformerSet2v" / "Background" / f"background{index}.png", TOWER / f"background-{index}.png")
    for series in ("A", "B", "C"):
        for index in range(1, 5):
            copy(DOWNLOADS / "PixelPlatformerSet2v" / "Anim" / f"torch{series}{index}.png", TOWER / f"torch-{series.lower()}-{index}.png")

    # High Forest 16x16 pack: first two mob-grind maps and HUD skin.
    high_forest_source = DOWNLOADS / "Legacy-Fantasy - High Forest 2.3"
    copy(high_forest_source / "Background" / "Background.png", HIGH_FOREST / "background.png")
    copy(high_forest_source / "Trees" / "Background.png", HIGH_FOREST / "tree-background.png")
    for name in ("Green-Tree.png", "Dark-Tree.png", "Golden-Tree.png", "Red-Tree.png", "Yellow-Tree.png"):
        copy(high_forest_source / "Trees" / name, HIGH_FOREST / name.lower().replace("-tree", "-tree"))
    copy(high_forest_source / "Assets" / "forest.png", HIGH_FOREST / "tiles.png")
    for name in ("Tree-Assets.png", "Props-Rocks.png", "Buildings.png", "Hive.png"):
        copy(high_forest_source / "Assets" / name, HIGH_FOREST / name.lower())
    copy(high_forest_source / "HUD" / "Base-01.png", UI / "highforest-hud.png")
    hud_source = UI / "highforest-hud.png"
    hud_slices = {
        "hud-panel-parchment.png": (0, 0, 64, 64),
        "hud-panel-strip-v.png": (64, 0, 80, 64),
        "hud-panel-strip-h.png": (0, 64, 64, 80),
        "hud-meter-red.png": (304, 0, 368, 16),
        "hud-meter-blue.png": (304, 48, 368, 64),
        "hud-meter-green.png": (304, 96, 368, 112),
        "hud-meter-gold.png": (304, 144, 368, 160),
        "hud-meter-brown.png": (304, 192, 368, 208),
        "hud-button-red.png": (240, 8, 304, 40),
        "hud-button-blue.png": (240, 56, 304, 88),
        "hud-button-green.png": (240, 104, 304, 136),
        "hud-button-gold.png": (240, 152, 304, 184),
        "hud-button-brown.png": (240, 200, 304, 232),
        "hud-board.png": (16, 224, 80, 288),
        "hud-chip-brown.png": (92, 12, 116, 36),
        "hud-chip-green.png": (92, 60, 116, 84),
        "hud-chip-blue.png": (92, 108, 116, 132),
        "hud-chip-gold.png": (92, 156, 116, 180),
        "hud-chip-gray.png": (92, 204, 116, 228),
        "hud-icon-diamond-gold.png": (136, 152, 168, 184),
        "hud-icon-diamond-blue.png": (136, 104, 168, 136),
        "hud-icon-diamond-green.png": (136, 56, 168, 88),
        "hud-icon-round-gold.png": (184, 152, 216, 184),
        "hud-icon-round-blue.png": (184, 104, 216, 136),
        "hud-icon-round-green.png": (184, 56, 216, 88),
    }
    for filename, box in hud_slices.items():
        slice_png(hud_source, UI / filename, box)
    forest_lite_bg = DOWNLOADS / "forest_tileset_lite" / "Sprites" / "Background"
    for name in ("sky_cloud.png", "cloud.png", "mountain2.png", "pine1.png", "pine2.png"):
        copy(forest_lite_bg / name, HIGH_FOREST / f"lite-{name}")

    # Pre-Tower cemetery pack: Blackbriar/Satyr gate and first tower grind map.
    pre_tower_source = DOWNLOADS / "Pre-Tower Mob Grind Map"
    for name in ("Background_0.png", "Background_1.png", "Grass_background_1.png", "Grass_background_2.png", "brush.png", "Salt.png"):
        copy(pre_tower_source / name, PRE_TOWER / name.lower().replace("_", "-"))
    copy(pre_tower_source / "graveyard.png", PRE_TOWER / "tiles.png")

    # Boss/enemy source and normalized runtime sheets. Runtime sheets use 64x64 fixed slots.
    satyr_sheet = DOWNLOADS / "SATYR_sprite_sheet " / "SPRITE_SHEET.png"
    copy(satyr_sheet, BOSSES / "satyr-source.png")
    copy(DOWNLOADS / "SATYR_sprite_sheet " / "SPRITE_PORTRAIT.png", BOSSES / "satyr-portrait.png")
    save_rows(
        satyr_sheet,
        RUNTIME / "boss-satyr.png",
        32,
        32,
        [
            [(0, column) for column in range(6)],              # idle/breathe
            [(1, column) for column in range(10)],             # walk/advance
            [(3, column) for column in range(7)],              # blade sweep
            [(9, column) for column in range(10)],             # dark cast
            [(6, column) for column in range(10)],             # collapse
        ],
        ["idle", "walk", "slash", "cast", "death"],
    )
    copy(TMP / "Fantasy Skeleton Enemies" / "Skeleton Warrior.png", BOSSES / "skeleton-warrior-source.png")
    copy(TMP / "Fantasy Skeleton Enemies" / "Skeleton Mage.png", BOSSES / "skeleton-mage-source.png")
    save_rows(
        TMP / "Fantasy Skeleton Enemies" / "Skeleton Warrior.png",
        RUNTIME / "enemy-tower-warrior.png",
        48,
        48,
        [[(0, column) for column in range(8)]],
        ["walk"],
    )
    save_rows(
        TMP / "Fantasy Skeleton Enemies" / "Skeleton Mage.png",
        RUNTIME / "enemy-tower-mage.png",
        48,
        48,
        [[(0, column) for column in range(8)]],
        ["walk"],
    )
    save_rows(
        high_forest_source / "Mob" / "Snail" / "walk-Sheet.png",
        RUNTIME / "enemy-forest-snail.png",
        48,
        32,
        [[(0, column) for column in range(8)]],
        ["walk"],
    )
    save_rows(
        high_forest_source / "Mob" / "Boar" / "Walk" / "Walk-Base-Sheet.png",
        RUNTIME / "enemy-forest-boar.png",
        48,
        32,
        [[(0, column) for column in range(6)]],
        ["walk"],
    )
    save_rows(
        high_forest_source / "Mob" / "Small Bee" / "Fly" / "Fly-Sheet.png",
        RUNTIME / "enemy-forest-bee.png",
        64,
        64,
        [[(0, column) for column in range(4)]],
        ["fly"],
    )

    # VFX sheets used by runtime.
    fx_sources = {
        "dark-vfx-1.png": TMP / "Dark VFX 1" / "Dark VFX 1 (40x32).png",
        "dark-vfx-2.png": TMP / "Dark VFX 2" / "Dark VFX 2 (48x64).png",
        "thunder-falcon.png": TMP / "Thunder Effect 01" / "Thunder Projectile 1" / "Thunder projectile1 wo blur.png",
        "thunder-impact.png": TMP / "Thunder Effect 01" / "Thunder Hit" / "Thunder hit wo blur.png",
        "thunder-strike.png": TMP / "Thunder Effect 02" / "Thunder Strike" / "Thunderstrike wo blur.png",
        "earth-impact.png": TMP / "Earth Effect 01" / "Impact Spritesheet.png",
        "wind-burst.png": TMP / "Wind Effect 02" / "Air Burst.png",
        "energy-ball.png": TMP / "Animation Pack" / "Energy ball" / "EnergyBall.png",
        "heal-spark.png": DOWNLOADS / "Heal Effect Sprite Sheet.png",
        "slash.png": DOWNLOADS / "Slash Sprite Sheet.png",
    }
    for filename, source in fx_sources.items():
        copy(source, FX / filename)


if __name__ == "__main__":
    main()
