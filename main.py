import pandas as pd
import ast
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

# === 1. Настройки ===

MOVIES_CSV = "tmdb_5000_movies.csv"
CREDITS_CSV = "tmdb_5000_credits.csv"
# MOVIES_CSV = "tmdb_5000_movies_short.csv"
# CREDITS_CSV = "tmdb_5000_credits_short.csv"
SCHEMA_TTL = "tmdb_schema.ttl"       # input
OUTPUT_TTL = "tmdb_data.ttl"         # сюда запишем индивиды

BASE = "http://example.org/film-rating#"
FR = Namespace(BASE)

# === 2. Загружаем схему ===

g = Graph()
g.parse(SCHEMA_TTL, format="turtle")
g.bind("fr", FR)

# === 3. Помощники для URI ===

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
    # job в URI лучше чуть почистить
    job_clean = str(job).lower().replace(" ", "_").replace("/", "_")
    return FR[f"crew/{int(movie_id)}_{int(person_id)}_{job_clean}"]

def safe_literal(value, datatype=None):
    if pd.isna(value):
        return None
    if datatype is None:
        return Literal(value)
    return Literal(value, datatype=datatype)

# === 4. Читаем данные ===

movies = pd.read_csv(MOVIES_CSV)
credits = pd.read_csv(CREDITS_CSV)

# переименуем title у movies, чтобы не конфликтовало с title у credits
movies = movies.rename(columns={"title": "movie_title"})
# credits.title нам не особо нужен — можно выкинуть
credits = credits.drop(columns=["title"])

# соединяем по id / movie_id
df = movies.merge(credits, left_on="id", right_on="movie_id", how="inner")

# === 5. Основной цикл по фильмам ===

for _, row in df.iterrows():
    mid = row["id"]
    m = movie_uri(mid)

    # тип
    g.add((m, RDF.type, FR.Movie))

    # простые dataprop
    if not pd.isna(row["movie_title"]):
        g.add((m, FR.movieTitle, Literal(row["movie_title"], datatype=XSD.string)))

    if not pd.isna(row["original_title"]):
        g.add((m, FR.originalTitle, Literal(row["original_title"], datatype=XSD.string)))

    if not pd.isna(row["budget"]):
        g.add((m, FR.budget, Literal(int(row["budget"]), datatype=XSD.integer)))

    if not pd.isna(row["revenue"]):
        g.add((m, FR.revenue, Literal(int(row["revenue"]), datatype=XSD.integer)))

    # материализуем profit
    if not pd.isna(row["budget"]) and not pd.isna(row["revenue"]):
        budget_val = int(row["budget"])
        revenue_val = int(row["revenue"])
        profit_val = revenue_val - budget_val
        # можно игнорировать отрицательную/нулевую прибыль, если не надо
        if profit_val > 0:
            g.add((m, FR.profit, Literal(profit_val, datatype=XSD.integer)))
    if not pd.isna(row["runtime"]):
        g.add((m, FR.runtime, Literal(float(row["runtime"]), datatype=XSD.decimal)))

    if not pd.isna(row["popularity"]):
        g.add((m, FR.popularity, Literal(float(row["popularity"]), datatype=XSD.decimal)))

    if not pd.isna(row["vote_average"]):
        g.add((m, FR.voteAverage, Literal(float(row["vote_average"]), datatype=XSD.decimal)))

    if not pd.isna(row["vote_count"]):
        g.add((m, FR.voteCount, Literal(int(row["vote_count"]), datatype=XSD.integer)))

    if not pd.isna(row["release_date"]):
        # формат в CSV: YYYY-MM-DD
        g.add((m, FR.releaseDate, Literal(row["release_date"], datatype=XSD.date)))

    # === genres ===
    if isinstance(row["genres"], str) and row["genres"].strip():
        try:
            genres_list = ast.literal_eval(row["genres"])
        except Exception:
            genres_list = []
        for gobj in genres_list:
            gid = gobj.get("id")
            gname = gobj.get("name")
            if gid is None:
                continue
            gen = genre_uri(gid)
            g.add((gen, RDF.type, FR.Genre))
            if gname:
                g.add((gen, FR.label, Literal(gname, datatype=XSD.string)))
            g.add((m, FR.hasGenre, gen))

    # === keywords ===
    if isinstance(row["keywords"], str) and row["keywords"].strip():
        try:
            kw_list = ast.literal_eval(row["keywords"])
        except Exception:
            kw_list = []
        for k in kw_list:
            kid = k.get("id")
            kname = k.get("name")
            if kid is None:
                continue
            kw = keyword_uri(kid)
            g.add((kw, RDF.type, FR.Keyword))
            if kname:
                g.add((kw, FR.label, Literal(kname, datatype=XSD.string)))
            g.add((m, FR.hasKeyword, kw))

    # === production_companies ===
    if isinstance(row["production_companies"], str) and row["production_companies"].strip():
        try:
            comps = ast.literal_eval(row["production_companies"])
        except Exception:
            comps = []
        for c in comps:
            cid = c.get("id")
            cname = c.get("name")
            if cid is None:
                continue
            comp = company_uri(cid)
            g.add((comp, RDF.type, FR.Company))
            if cname:
                g.add((comp, FR.label, Literal(cname, datatype=XSD.string)))
            g.add((m, FR.producedBy, comp))

    # === production_countries ===
    if isinstance(row["production_countries"], str) and row["production_countries"].strip():
        try:
            countries = ast.literal_eval(row["production_countries"])
        except Exception:
            countries = []
        for c in countries:
            code = c.get("iso_3166_1")
            cname = c.get("name")
            if not code:
                continue
            cou = country_uri(code)
            g.add((cou, RDF.type, FR.Country))
            if cname:
                g.add((cou, FR.label, Literal(cname, datatype=XSD.string)))
            g.add((m, FR.producedInCountry, cou))

    # === spoken_languages ===
    if isinstance(row["spoken_languages"], str) and row["spoken_languages"].strip():
        try:
            langs = ast.literal_eval(row["spoken_languages"])
        except Exception:
            langs = []
        for l in langs:
            code = l.get("iso_639_1")
            lname = l.get("name")
            if not code:
                continue
            lang = language_uri(code)
            g.add((lang, RDF.type, FR.Language))
            if lname:
                g.add((lang, FR.label, Literal(lname, datatype=XSD.string)))
            g.add((m, FR.spokenLanguage, lang))

    # === cast ===
    if isinstance(row["cast"], str) and row["cast"].strip():
        try:
            cast_list = ast.literal_eval(row["cast"])
        except Exception:
            cast_list = []
        for c in cast_list:
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
                g.add((role, FR.characterName,
                       Literal(character, datatype=XSD.string)))
            g.add((role, FR.castOrder,
                   Literal(int(order), datatype=XSD.integer)))

    # === crew ===
    if isinstance(row["crew"], str) and row["crew"].strip():
        try:
            crew_list = ast.literal_eval(row["crew"])
        except Exception:
            crew_list = []
        for c in crew_list:
            pid = c.get("id")
            pname = c.get("name")
            job = c.get("job")
            dept = c.get("department")

            if pid is None:
                continue

            person = person_uri(pid)
            g.add((person, RDF.type, FR.Person))
            if pname:
                g.add((person, FR.label, Literal(pname, datatype=XSD.string)))

            role = crew_role_uri(mid, pid, job or "unknown")
            g.add((role, RDF.type, FR.CrewRole))
            g.add((m, FR.hasCrew, role))
            g.add((role, FR.creditsPerson, person))
            if job:
                g.add((role, FR.crewJob,
                       Literal(job, datatype=XSD.string)))
            if dept:
                g.add((role, FR.crewDepartment,
                       Literal(dept, datatype=XSD.string)))

            # director
            if job and "director" in job.lower():
                g.add((m, FR.directedBy, person))

# === 6. Сохраняем граф ===

g.serialize(OUTPUT_TTL, format="turtle")
print(f"Saved data ontology to {OUTPUT_TTL}")
