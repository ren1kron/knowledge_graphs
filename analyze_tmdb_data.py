#!/usr/bin/env python3
import pandas as pd
import ast
from collections import Counter

MOVIES_CSV = "tmdb_5000_movies.csv"
CREDITS_CSV = "tmdb_5000_credits.csv"

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 200)


def safe_parse_list(value):
    """
    tmdb поля (genres, keywords, cast, crew, ...) — это строки вида:
    "[{'id': 28, 'name': 'Action'}, ...]"
    После чтения через pandas это обычно валидный Python-литерал.
    """
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        return ast.literal_eval(value)
    except Exception:
        return []


def analyze_movies(path: str = MOVIES_CSV):
    print("=== Анализ tmdb_5000_movies.csv ===")
    movies = pd.read_csv(path, low_memory=False)
    print(f"Всего фильмов: {len(movies)}")
    print("\nКолонки:")
    print(movies.columns.tolist())

    # Пропуски по ключевым полям
    key_cols = [
        "budget",
        "revenue",
        "genres",
        "keywords",
        "runtime",
        "vote_average",
        "vote_count",
        "popularity",
        "production_companies",
        "production_countries",
        "spoken_languages",
    ]
    print("\nДоля пропусков по важным колонкам:")
    missing = movies[key_cols].isna().mean().sort_values(ascending=False)
    print(missing)

    # Базовая статистика по численным полям
    num_cols = ["budget", "revenue", "runtime", "vote_average", "vote_count", "popularity"]
    print("\nБазовая статистика по численным полям:")
    print(movies[num_cols].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.99]))

    # Разбор жанров
    all_genres = Counter()
    for s in movies["genres"]:
        for g in safe_parse_list(s):
            name = g.get("name")
            if name:
                all_genres[name] += 1

    print("\nТоп-20 жанров по количеству фильмов:")
    for genre, cnt in all_genres.most_common(20):
        print(f"{genre:25s} {cnt:5d}")

    # Пример: сколько жанров в среднем у фильма
    num_genres_per_movie = movies["genres"].apply(lambda s: len(safe_parse_list(s)))
    print("\nСколько жанров на фильм (описательная статистика):")
    print(num_genres_per_movie.describe())

    return movies


def explode_credits(credits: pd.DataFrame):
    """
    Разворачиваем cast и crew в таблички:
    - cast_exploded: одна строка на актёра в фильме
    - crew_exploded: одна строка на члена съёмочной группы в фильме
    """
    # CAST
    cast_records = []
    for _, row in credits.iterrows():
        movie_id = row["movie_id"]
        title = row["title"]
        for c in safe_parse_list(row["cast"]):
            cast_records.append({
                "movie_id": movie_id,
                "movie_title": title,
                "person_id": c.get("id"),
                "person_name": c.get("name"),
                "character": c.get("character"),
                "order": c.get("order"),
                "cast_id": c.get("cast_id"),
                "gender": c.get("gender"),
            })
    cast_exploded = pd.DataFrame(cast_records)

    # CREW
    crew_records = []
    for _, row in credits.iterrows():
        movie_id = row["movie_id"]
        title = row["title"]
        for c in safe_parse_list(row["crew"]):
            crew_records.append({
                "movie_id": movie_id,
                "movie_title": title,
                "person_id": c.get("id"),
                "person_name": c.get("name"),
                "job": c.get("job"),
                "department": c.get("department"),
                "credit_id": c.get("credit_id"),
                "gender": c.get("gender"),
            })
    crew_exploded = pd.DataFrame(crew_records)

    return cast_exploded, crew_exploded


def analyze_credits(path: str = CREDITS_CSV):
    print("\n=== Анализ tmdb_5000_credits.csv ===")
    credits = pd.read_csv(path, low_memory=False)
    print(f"Всего записей в credits (по фильмам): {len(credits)}")
    print("Колонки:", credits.columns.tolist())

    cast_exploded, crew_exploded = explode_credits(credits)

    print(f"\nCast (актёры): {len(cast_exploded)} строк (actor-in-movie)")
    print(f"Crew (съёмочная группа): {len(crew_exploded)} строк (crew-member-in-movie)")

    # Сколько актёров / членов съёмочной группы на фильм
    cast_per_movie = cast_exploded.groupby("movie_id")["person_id"].nunique()
    crew_per_movie = crew_exploded.groupby("movie_id")["person_id"].nunique()

    print("\nСколько актёров на фильм (уникальных people):")
    print(cast_per_movie.describe())

    print("\nСколько членов съёмочной группы на фильм (уникальных people):")
    print(crew_per_movie.describe())

    # Топ job'ов
    print("\nТоп-40 job (должностей) в crew:")
    job_counts = crew_exploded["job"].value_counts().head(40)
    print(job_counts)

    # Топ департаментов
    print("\nТоп департаментов в crew:")
    dept_counts = crew_exploded["department"].value_counts()
    print(dept_counts)

    # job × department (для проектирования онтологии ролей)
    job_dept = (
        crew_exploded
        .groupby(["job", "department"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    # Сохраняем, чтобы удобно смотреть в Excel/LibreOffice
    job_counts.to_csv("crew_jobs_stats.csv", header=["count"])
    job_dept.to_csv("crew_job_department_stats.csv", index=False)

    # Немного статистики по cast (главные роли и т.п.)
    print("\nРаспределение значения 'order' в cast (позиция актёра в титрах):")
    print(cast_exploded["order"].describe())

    # Топ-30 актёрских персонажей по частоте (просто как пример)
    char_counts = cast_exploded["character"].value_counts().head(30)
    char_counts.to_csv("cast_character_stats.csv", header=["count"])

    cast_exploded.to_csv("cast_exploded_sample.csv", index=False)
    crew_exploded.to_csv("crew_exploded_sample.csv", index=False)

    print("\nСводки сохранены в файлы:")
    print("  - crew_jobs_stats.csv (job -> count)")
    print("  - crew_job_department_stats.csv (job, department, count)")
    print("  - cast_character_stats.csv (character -> count)")
    print("  - cast_exploded_sample.csv (полная 'плоская' cast-таблица)")
    print("  - crew_exploded_sample.csv (полная 'плоская' crew-таблица)")

    return credits, cast_exploded, crew_exploded


def main():
    movies = analyze_movies(MOVIES_CSV)
    credits, cast_exploded, crew_exploded = analyze_credits(CREDITS_CSV)

    # Здесь можно дописать любые дополнительные анализы под твои CQs.
    # Например: какие job'ы чаще всего встречаются в департаменте "Directing":
    directing_jobs = (
        crew_exploded[crew_exploded["department"] == "Directing"]["job"]
        .value_counts()
        .head(20)
    )
    print("\nТоп-20 job в департаменте Directing:")
    print(directing_jobs)

    # Или в департаменте Writing:
    writing_jobs = (
        crew_exploded[crew_exploded["department"] == "Writing"]["job"]
        .value_counts()
        .head(20)
    )
    print("\nТоп-20 job в департаменте Writing:")
    print(writing_jobs)

    print("\nГотово. Посмотри CSV-шки, чтобы спроектировать сущности ролей (Director, Screenwriter, Producer и т.д.).")


if __name__ == "__main__":
    main()
