#!/usr/bin/env python3
import pandas as pd
import ast
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

# === Пути к файлам ===
MOVIES_CSV = "tmdb_5000_movies.csv"
CREDITS_CSV = "tmdb_5000_credits.csv"
SCHEMA_TTL = "tmdb_schema.ttl"       # базовый файл со схемой
OUTPUT_TTL = "tmdb_data_with_roles.ttl"

BASE = "http://example.org/film-rating#"
FR = Namespace(BASE)


# === Вспомогательные функции ===

def safe_parse_list(value):
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        return ast.literal_eval(value)
    except Exception:
        return []


def movie_uri(movie_id):
    return FR[f"movie/{int(movie_id)}"]


def person_uri(person_id):
    return FR[f"person/{int(person_id)}"]


def genre_uri(genre_id):
    return FR[f"genre/{int(genre_id)}"]


def company_uri(comp_id):
    return FR[f"company/{int(comp_id)}"]


def country_uri(code):
    return FR[f"country/{code}"]


def language_uri(code):
    return FR[f"lang/{code}"]


def keyword_uri(kw_id):
    return FR[f"keyword/{int(kw_id)}"]


def cast_role_uri(movie_id, person_id, order):
    return FR[f"cast/{int(movie_id)}_{int(person_id)}_{int(order)}"]


def crew_role_uri(movie_id, person_id, job):
    job_clean = str(job).lower().replace(" ", "_").replace("/", "_")
    return FR[f"crew/{int(movie_id)}_{int(person_id)}_{job_clean}"]


def role_type_uri(canonical_role: str):
    # canonical_role вроде "Director", "Producer", "Screenwriter" etc.
    return FR[f"role/{canonical_role}"]


# === Маппинг job + department → canonical_role ===

DEFAULT_ROLE = "OtherCrewRole"

CANONICAL_ROLE_MAP = {
    # --- Directing ---
    ("Director", "Directing"): "Director",
    ("Co-Director", "Directing"): "Director",
    ("Assistant Director", "Directing"): "AssistantDirector",
    ("First Assistant Director", "Directing"): "AssistantDirector",
    ("Second Assistant Director", "Directing"): "AssistantDirector",
    ("Third Assistant Director", "Directing"): "AssistantDirector",

    # --- Writing / сценарий ---
    ("Screenplay", "Writing"): "Screenwriter",
    ("Screenstory", "Writing"): "Screenwriter",
    ("Teleplay", "Writing"): "Screenwriter",
    ("Writer", "Writing"): "WriterRole",
    ("Story", "Writing"): "StoryAuthor",
    ("Original Story", "Writing"): "StoryAuthor",
    ("Novel", "Writing"): "SourceAuthor",
    ("Author", "Writing"): "SourceAuthor",
    ("Book", "Writing"): "SourceAuthor",
    ("Comic Book", "Writing"): "SourceAuthor",
    ("Adaptation", "Writing"): "Adapter",
    ("Scenario Writer", "Writing"): "Screenwriter",

    # --- Production / продюсеры ---
    ("Producer", "Production"): "Producer",
    ("Executive Producer", "Production"): "ExecutiveProducer",
    ("Co-Producer", "Production"): "CoProducer",
    ("Associate Producer", "Production"): "AssociateProducer",
    ("Line Producer", "Production"): "LineProducer",
    ("Unit Production Manager", "Production"): "ProductionManager",

    # --- Музыка ---
    ("Original Music Composer", "Sound"): "Composer",
    ("Music", "Sound"): "Composer",
    ("Music Editor", "Sound"): "MusicEditor",

    # --- Монтаж ---
    ("Editor", "Editing"): "Editor",

    # --- Камера ---
    ("Director of Photography", "Camera"): "Cinematographer",
    ("Camera Operator", "Camera"): "CameraOperator",
    ("Still Photographer", "Camera"): "StillPhotographer",

    # --- Кастинг ---
    ("Casting", "Production"): "CastingDirector",

    # --- Художники ---
    ("Production Design", "Art"): "ProductionDesigner",
    ("Art Direction", "Art"): "ArtDirector",
    ("Set Decoration", "Art"): "SetDecorator",

    # --- Костюмы / грим ---
    ("Costume Design", "Costume & Make-Up"): "CostumeDesigner",
    ("Makeup Artist", "Costume & Make-Up"): "MakeupArtist",
    ("Hairstylist", "Costume & Make-Up"): "HairStylist",
    ("Costume Supervisor", "Costume & Make-Up"): "CostumeSupervisor",
    ("Set Costumer", "Costume & Make-Up"): "SetCostumer",

    # --- VFX ---
    ("Visual Effects Supervisor", "Visual Effects"): "VFXSupervisor",
    ("Visual Effects Producer", "Visual Effects"): "VFXProducer",
}

def get_canonical_role(job: str, department: str) -> str:
    key = (job, department)
    if key in CANONICAL_ROLE_MAP:
        return CANONICAL_ROLE_MAP[key]
    # Можно попробовать по одному job без департамента, если захочешь расширить
    for (j, d), role in CANONICAL_ROLE_MAP.items():
        if j == job and (d is None or d == department):
            return role
    return DEFAULT_ROLE


# === Основной скрипт ===

def main():
    # 1. Грузим схему
    g = Graph()
    g.parse(SCHEMA_TTL, format="turtle")
    g.bind("fr", FR)

    # 1.1. Добавляем определения RoleType и самих канонических ролей
    g.add((FR.RoleType, RDF.type, RDFS.Class))
    g.add((FR.roleType, RDF.type, RDF.Property))
    g.add((FR.roleType, RDFS.domain, FR.CrewRole))
    g.add((FR.roleType, RDFS.range, FR.RoleType))

    for canonical_role in sorted(set(CANONICAL_ROLE_MAP.values()) | {DEFAULT_ROLE}):
        rt = role_type_uri(canonical_role)
        g.add((rt, RDF.type, FR.RoleType))
        g.add((rt, FR.label, Literal(canonical_role, datatype=XSD.string)))

    # 2. Читаем CSV
    movies = pd.read_csv(MOVIES_CSV, low_memory=False)
    credits = pd.read_csv(CREDITS_CSV, low_memory=False)
    df = movies.merge(credits, left_on="id", right_on="movie_id", how="inner")

    for _, row in df.iterrows():
        mid = row["id"]
        m = movie_uri(mid)
        g.add((m, RDF.type, FR.Movie))

        # ======== DATAPROPS (как раньше) =========
        if isinstance(row.get("title"), str):
            g.add((m, FR.movieTitle, Literal(row["title"], datatype=XSD.string)))
        if isinstance(row.get("original_title"), str):
            g.add((m, FR.originalTitle, Literal(row["original_title"], datatype=XSD.string)))

        for col, prop, dtype in [
            ("budget", FR.budget, XSD.integer),
            ("revenue", FR.revenue, XSD.integer),
            ("runtime", FR.runtime, XSD.decimal),
            ("popularity", FR.popularity, XSD.decimal),
            ("vote_average", FR.voteAverage, XSD.decimal),
            ("vote_count", FR.voteCount, XSD.integer),
        ]:
            val = row.get(col)
            if pd.notna(val):
                g.add((m, prop, Literal(float(val) if dtype == XSD.decimal else int(val), datatype=dtype)))

        if isinstance(row.get("release_date"), str) and row["release_date"]:
            g.add((m, FR.releaseDate, Literal(row["release_date"], datatype=XSD.date)))

        # ======== Genres ========
        for gobj in safe_parse_list(row.get("genres", "")):
            gid = gobj.get("id")
            gname = gobj.get("name")
            if gid is None:
                continue
            gen = genre_uri(gid)
            g.add((gen, RDF.type, FR.Genre))
            if gname:
                g.add((gen, FR.label, Literal(gname, datatype=XSD.string)))
            g.add((m, FR.hasGenre, gen))

        # ======== Keywords ========
        for k in safe_parse_list(row.get("keywords", "")):
            kid = k.get("id")
            kname = k.get("name")
            if kid is None:
                continue
            kw = keyword_uri(kid)
            g.add((kw, RDF.type, FR.Keyword))
            if kname:
                g.add((kw, FR.label, Literal(kname, datatype=XSD.string)))
            g.add((m, FR.hasKeyword, kw))

        # ======== Companies ========
        for c in safe_parse_list(row.get("production_companies", "")):
            cid = c.get("id")
            cname = c.get("name")
            if cid is None:
                continue
            comp = company_uri(cid)
            g.add((comp, RDF.type, FR.Company))
            if cname:
                g.add((comp, FR.label, Literal(cname, datatype=XSD.string)))
            g.add((m, FR.producedBy, comp))

        # ======== Countries ========
        for c in safe_parse_list(row.get("production_countries", "")):
            code = c.get("iso_3166_1")
            cname = c.get("name")
            if not code:
                continue
            cou = country_uri(code)
            g.add((cou, RDF.type, FR.Country))
            if cname:
                g.add((cou, FR.label, Literal(cname, datatype=XSD.string)))
            g.add((m, FR.producedInCountry, cou))

        # ======== Languages ========
        for l in safe_parse_list(row.get("spoken_languages", "")):
            code = l.get("iso_639_1")
            lname = l.get("name")
            if not code:
                continue
            lang = language_uri(code)
            g.add((lang, RDF.type, FR.Language))
            if lname:
                g.add((lang, FR.label, Literal(lname, datatype=XSD.string)))
            g.add((m, FR.spokenLanguage, lang))

        # ======== CAST (оставляем как раньше) ========
        for c in safe_parse_list(row.get("cast", "")):
            pid = c.get("id")
            pname = c.get("name")
            character = c.get("character")
            order = c.get("order", 0)

            if pid is None:
                continue

            person = person_uri(pid)
            g.add((person, RDF.type, FR.Person))
            if pname:
                g.add((person, FR.label, Literal(pname, datatype=XSD.string)))

            role = cast_role_uri(mid, pid, order)
            g.add((role, RDF.type, FR.CastRole))
            g.add((m, FR.hasCast, role))
            g.add((role, FR.playedBy, person))
            if character:
                g.add((role, FR.characterName, Literal(character, datatype=XSD.string)))
            g.add((role, FR.castOrder, Literal(int(order), datatype=XSD.integer)))

        # ======== CREW с каноническими ролями ========
        for c in safe_parse_list(row.get("crew", "")):
            pid = c.get("id")
            pname = c.get("name")
            job = c.get("job")
            dept = c.get("department")

            if pid is None or not job:
                continue

            person = person_uri(pid)
            g.add((person, RDF.type, FR.Person))
            if pname:
                g.add((person, FR.label, Literal(pname, datatype=XSD.string)))

            crew_ind = crew_role_uri(mid, pid, job)
            g.add((crew_ind, RDF.type, FR.CrewRole))
            g.add((m, FR.hasCrew, crew_ind))
            g.add((crew_ind, FR.creditsPerson, person))

            # job/department как датапропы (если хочешь)
            g.add((crew_ind, FR.crewJob, Literal(job, datatype=XSD.string)))
            if dept:
                g.add((crew_ind, FR.crewDepartment, Literal(dept, datatype=XSD.string)))

            # канонический тип роли
            canonical = get_canonical_role(job, dept)
            rt = role_type_uri(canonical)
            g.add((crew_ind, FR.roleType, rt))

    # 3. Сохраняем граф
    g.serialize(OUTPUT_TTL, format="turtle")
    print(f"Saved ontology with roles to {OUTPUT_TTL}")


if __name__ == "__main__":
    main()
