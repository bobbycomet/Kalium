"""Multi-game Steam depot manifests for downpatching / version pinning.

Games: Skyrim SE, Fallout 4, Starfield, Cyberpunk 2077, The Witcher 3.

Each target lists (depot_id, manifest_id) tuples. Optional DLC depots are
included where the user provided them — only download DLC depots you own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class BackpatchTarget:
    """One selectable version for a game."""
    id: str
    label: str
    depots: tuple[tuple[int, int], ...]  # (depot_id, manifest_id)
    notes: str = ""
    # Optional depots (DLC / language) — shown in commands but marked optional
    optional_depots: tuple[tuple[int, int, str], ...] = ()  # (depot, manifest, label)


@dataclass(frozen=True)
class BackpatchGame:
    id: str
    name: str
    app_id: int
    exe_names: tuple[str, ...]
    folder_hint: str
    targets: tuple[BackpatchTarget, ...]
    default_target: str = ""

    def target_ids(self) -> list[str]:
        return [t.id for t in self.targets]

    def get_target(self, version: str) -> BackpatchTarget:
        v = (version or "").strip()
        for t in self.targets:
            if t.id == v or t.label == v:
                return t
        # alias: strip leading v
        if v.lower().startswith("v"):
            v2 = v[1:]
            for t in self.targets:
                if t.id == v2:
                    return t
        raise ValueError(
            f"Unknown version {version!r} for {self.name}. "
            f"Choose: {', '.join(self.target_ids())}"
        )


# ---------------------------------------------------------------------------
# Skyrim Special Edition (489830) — existing Kalium targets
# ---------------------------------------------------------------------------
_SKYRIM = BackpatchGame(
    id="skyrim-se",
    name="Skyrim Special Edition",
    app_id=489830,
    exe_names=("SkyrimSE.exe", "SkyrimSELauncher.exe"),
    folder_hint="/path/to/Skyrim Special Edition",
    default_target="1.6.1170",
    targets=(
        BackpatchTarget(
            "1.6.1170",
            "1.6.1170 (recommended for AE 1.6.x mods)",
            ((489833, 1914580699073641964),),
        ),
        BackpatchTarget(
            "1.6.1130",
            "1.6.1130",
            ((489833, 2442187225363891157),),
        ),
        BackpatchTarget(
            "1.6.640",
            "1.6.640",
            ((489833, 5291801952219815735),),
        ),
        BackpatchTarget(
            "1.5.97",
            "1.5.97 (pre-AE / maximum legacy mod compatibility)",
            (
                (489831, 7848722008564294070),
                (489832, 8702665189575304780),
                (489833, 2289561010626853674),
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Fallout 4 (377160)
# ---------------------------------------------------------------------------
_FALLOUT4 = BackpatchGame(
    id="fallout4",
    name="Fallout 4",
    app_id=377160,
    exe_names=("Fallout4.exe", "Fallout4Launcher.exe"),
    folder_hint="/path/to/Fallout 4",
    default_target="1.10.163",
    targets=(
        BackpatchTarget(
            "1.10.163",
            "1.10.163 Pre-Next-Gen (best for older F4SE plugins)",
            (
                (377162, 5847529232406005096),
                (377161, 7497069378349273908),
                (377163, 5819088023757897745),
                (377164, 2178106366609958945),
            ),
            notes="Base game only. Add optional DLC depots below if owned.",
            optional_depots=(
                (435870, 1691678129192680960, "Automatron"),
                (435871, 5106118861901111234, "Wasteland Workshop"),
                (435880, 1255562923187931216, "Far Harbor"),
                (435881, 1207717296920736193, "Nuka-World / other DLC pack"),
            ),
        ),
        BackpatchTarget(
            "1.10.984",
            "1.10.984 First Next-Gen",
            (
                (377162, 5698952341602575696),
                (377161, 7332110922360867314),
                (377163, 8681102885670959037),
                (377164, 8492427313392140315),
            ),
            optional_depots=(
                (435870, 1213339795579796878, "Automatron"),
                (435871, 7785009542965564688, "Wasteland Workshop"),
                (435880, 366079256218893805, "Far Harbor"),
            ),
        ),
        BackpatchTarget(
            "1.11.191",
            "1.11.191",
            (
                (377162, 5433405173062582852),
                (377161, 5983086794954940044),
                (377163, 8360827888850301367),
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Starfield (1716740)
# ---------------------------------------------------------------------------
_STARFIELD = BackpatchGame(
    id="starfield",
    name="Starfield",
    app_id=1716740,
    exe_names=("Starfield.exe",),
    folder_hint="/path/to/Starfield",
    default_target="1.11.33",
    targets=(
        BackpatchTarget(
            "1.7.23",
            "1.7.23 Day 1 / Early Access",
            (
                (1716741, 4447793252473787578),
                (1716742, 3741876378906932066),
            ),
            notes="Depots 1716741 (engine/exe) + 1716742 (Data).",
            optional_depots=(
                (2401180, 0, "Digital Premium Edition (manifest TBD — only if owned)"),
                (2401181, 0, "Pre-order bonus (manifest TBD — only if owned)"),
                (2721670, 0, "Shattered Space DLC (manifest TBD — only if owned)"),
            ),
        ),
        BackpatchTarget(
            "1.7.33",
            "1.7.33 Pre-Patch Exploits",
            (
                (1716741, 3276175983502685135),
                (1716742, 7068708531301311719),
            ),
        ),
        BackpatchTarget(
            "1.11.33",
            "1.11.33 May 2024 Maps & 60 FPS",
            (
                (1716741, 6120194849202581691),
                (1716742, 5161319454857509031),
            ),
        ),
        BackpatchTarget(
            "1.12.30",
            "1.12.30 Creation Kit Base",
            (
                (1716741, 1598282381284562097),
                (1716742, 8882583849762193821),
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Cyberpunk 2077 (1091500) + Phantom Liberty app 2138330 when applicable
# ---------------------------------------------------------------------------
_CYBERPUNK = BackpatchGame(
    id="cyberpunk2077",
    name="Cyberpunk 2077",
    app_id=1091500,
    exe_names=("Cyberpunk2077.exe",),
    folder_hint="/path/to/Cyberpunk 2077",
    default_target="2.12",
    targets=(
        BackpatchTarget(
            "2.12",
            "2.12 (2024-02-29)",
            (
                (1091500, 7064272183201416489),
                (1091501, 3935102684525872303),
                (2138330, 5094071097429923087),  # Phantom Liberty — skip if not owned
            ),
            notes="Includes Phantom Liberty depot 2138330 — omit if you do not own the DLC. "
            "App 1091500 is used for base depots; PL uses app 2138330.",
        ),
        BackpatchTarget(
            "2.11",
            "2.11 (2024-01-31)",
            (
                (1091500, 3794356023348169123),
                (1091501, 415651277559119937),
                (2138330, 1247263585971652529),
            ),
        ),
        BackpatchTarget(
            "2.10",
            "2.10 / 2.1 (2023-12-05)",
            (
                (1091500, 2413725515324546419),
                (1091501, 2238892413801664242),
                (2138330, 8336407654663849967),
            ),
        ),
        BackpatchTarget(
            "2.02",
            "2.02 (2023-10-26)",
            (
                (1091500, 6842514930198695842),
                (1091501, 4882158097132343077),
                (2138330, 255755420818251691),
            ),
        ),
        BackpatchTarget(
            "2.01",
            "2.01 (2023-10-05)",
            (
                (1091500, 4899876251458925341),
                (1091501, 8933391217277873539),
                (2138330, 1990018461669282288),
            ),
        ),
        BackpatchTarget(
            "2.00",
            "2.00 (2023-09-21)",
            (
                (1091500, 7586520112461876542),
                (1091501, 7695458851217910405),
                (2138330, 4702299018468121610),
            ),
        ),
        BackpatchTarget(
            "1.63",
            "1.63 Hotfix 2 legacy (pre-2.0, no PL)",
            (
                (1091500, 8111956108197775586),
                (1091501, 3272971206132717088),
            ),
            notes="Also available via Steam Betas → 1_63_legacy_patch without console.",
        ),
        BackpatchTarget(
            "1.52",
            "1.52 (2022-03-22)",
            (
                (1091500, 523363065099307767),
                (1091501, 3517958835290722458),
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# The Witcher 3 — Standard Edition 292030
# ---------------------------------------------------------------------------
_WITCHER3 = BackpatchGame(
    id="witcher3",
    name="The Witcher 3",
    app_id=292030,
    exe_names=("witcher3.exe", "Witcher3.exe"),
    folder_hint="/path/to/The Witcher 3 Wild Hunt",
    default_target="1.32",
    targets=(
        BackpatchTarget(
            "1.32",
            "1.32 Classic Pre-Next-Gen (best for older mods)",
            (
                (292031, 2633003023223030386),  # core
                (292032, 8056213768224726292),  # English text/audio
            ),
            notes="Core + English language depots. GOTY owners may use App 499450 instead.",
            optional_depots=(
                (378640, 4015694723048560111, "Hearts of Stone"),
                (378648, 8345719323788730953, "Blood and Wine"),
            ),
        ),
        BackpatchTarget(
            "1.31",
            "1.31 GOTY Classic",
            (
                (292031, 8680323326164284521),
                (292032, 8056213768224726292),
            ),
            optional_depots=(
                (378640, 4015694723048560111, "Hearts of Stone"),
                (378648, 8345719323788730953, "Blood and Wine"),
            ),
        ),
        BackpatchTarget(
            "4.00",
            "4.00 Initial Next-Gen",
            (
                (292031, 4522967262060378059),
                (292032, 6023773199859560416),
            ),
        ),
        BackpatchTarget(
            "4.01",
            "4.01 Next-Gen Patch 1",
            (
                (292031, 7918884940562425514),
                (292032, 6023773199859560416),
            ),
        ),
        BackpatchTarget(
            "4.02",
            "4.02 Next-Gen Patch 2",
            (
                (292031, 2309852233267073235),
                (292032, 6023773199859560416),
            ),
        ),
        BackpatchTarget(
            "4.03",
            "4.03 Next-Gen Patch 3",
            (
                (292031, 1610488273641249767),
                (292032, 6023773199859560416),
            ),
        ),
        BackpatchTarget(
            "4.04",
            "4.04 REDkit / Steam Workshop",
            (
                (292031, 7524807930142120913),
                (292032, 6023773199859560416),
            ),
        ),
        # GOTY edition package (App 499450) — classic 1.32
        BackpatchTarget(
            "1.32-goty",
            "1.32 GOTY Edition package (App 499450)",
            (
                (499451, 8680323326164284521),
                (504901, 3288127393455986872),
                (499455, 1071222468431927295),
            ),
            notes="Standalone GOTY AppID 499450 — use only if that is the package you own.",
        ),
    ),
)

BACKPATCH_GAMES: tuple[BackpatchGame, ...] = (
    _SKYRIM,
    _FALLOUT4,
    _STARFIELD,
    _CYBERPUNK,
    _WITCHER3,
)

_BY_ID = {g.id: g for g in BACKPATCH_GAMES}
_BY_APP = {g.app_id: g for g in BACKPATCH_GAMES}


def list_games() -> list[BackpatchGame]:
    return list(BACKPATCH_GAMES)


def get_game(game_id: str) -> BackpatchGame:
    g = _BY_ID.get(game_id)
    if g:
        return g
    # allow name fragment
    low = game_id.lower().strip()
    for g in BACKPATCH_GAMES:
        if low in g.id or low in g.name.lower():
            return g
    raise ValueError(f"Unknown game {game_id!r}. Choose: {', '.join(_BY_ID)}")


def get_game_by_app_id(app_id: int | str) -> Optional[BackpatchGame]:
    return _BY_APP.get(int(app_id))


def steam_console_commands(
    game_id: str,
    version: str,
    *,
    include_optional: bool = False,
    include_notes: bool = True,
) -> str:
    """
    Build download_depot lines for Steam console.

    Cyberpunk Phantom Liberty and some optional depots use a *different* app id
    than the base game; those lines use the depot id as the first number when
    depot_id looks like an app (common Steam convention for DLC apps).
    """
    game = get_game(game_id)
    target = game.get_target(version)
    lines: list[str] = []
    if include_notes and target.notes:
        lines.append(f"# {target.notes}")
    lines.append(f"# {game.name} → {target.label}")
    lines.append(f"# AppID {game.app_id}")

    for depot_id, manifest in target.depots:
        # Cyberpunk PL: depot 2138330 is under app 2138330
        app = game.app_id
        if game.id == "cyberpunk2077" and depot_id == 2138330:
            app = 2138330
        elif game.id == "witcher3" and target.id == "1.32-goty":
            app = 499450
        lines.append(f"download_depot {app} {depot_id} {manifest}")

    if include_optional and target.optional_depots:
        lines.append("# --- optional (only if owned) ---")
        for depot_id, manifest, label in target.optional_depots:
            if manifest == 0:
                lines.append(f"# {label}: depot {depot_id} (manifest not listed — look up if needed)")
                continue
            lines.append(f"download_depot {game.app_id} {depot_id} {manifest}  # {label}")

    return "\n".join(lines)


def depots_for(game_id: str, version: str) -> list[tuple[int, int]]:
    return list(get_game(game_id).get_target(version).depots)
