from rdflib import Graph, Namespace
import time
from rdflib.plugins.sparql import prepareQuery

# Параметры
RDF_FILE = 'tmdb_data.ttl'


# Загрузка RDF графа
def load_graph(file_path):
    g = Graph()
    g.parse(file_path, format='turtle')  # используем turtle, так как схема в TTL
    return g


# Настройка пространства имен
def setup_namespace(graph):
    fr_namespace = "http://example.org/film-rating#"
    fr = Namespace(fr_namespace)
    graph.bind('fr', fr)
    graph.bind('rdf', Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"))
    graph.bind('rdfs', Namespace("http://www.w3.org/2000/01/rdf-schema#"))
    graph.bind('xsd', Namespace("http://www.w3.org/2001/XMLSchema#"))
    return fr


# Выполнение SPARQL-запроса с таймингом
def execute_query(graph, query, query_name, timeout=60):
    print(f"\n{'=' * 60}")
    print(f"Запрос: {query_name}")
    print(f"{'=' * 60}")

    start_time = time.time()

    try:
        # Используем prepareQuery для оптимизации
        prepared_query = prepareQuery(query)
        results = graph.query(prepared_query)

        elapsed_time = time.time() - start_time
        print(f"Время выполнения: {elapsed_time:.2f} сек")

        if len(results) == 0:
            print("Результатов не найдено")
            return

        # Выводим заголовки
        print("\nРезультаты:")
        print("-" * 80)

        # Преобразуем результаты в список для лучшего форматирования
        rows = []
        for row in results:
            rows.append(row)

        # Определяем ширину колонок
        if len(rows) > 0:
            col_widths = [0] * len(rows[0])
            for row in rows:
                for i, val in enumerate(row):
                    col_widths[i] = max(col_widths[i], len(str(val)))

            # Выводим заголовки
            for i, var in enumerate(results.vars):
                print(f"{var:<{col_widths[i]}}", end="  ")
            print()
            print("-" * sum(col_widths) + "--" * len(col_widths))

            # Выводим данные
            for row in rows:
                for i, val in enumerate(row):
                    print(f"{val:<{col_widths[i]}}", end="  ")
                print()

        print(f"\nНайдено записей: {len(rows)}")

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"Ошибка при выполнении запроса (время: {elapsed_time:.2f} сек): {e}")


# Проверка существующих данных
def check_data_structure(graph, fr):
    """Проверка структуры данных для отладки"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА СТРУКТУРЫ ДАННЫХ")
    print("=" * 60)

    # Проверяем какие жанры существуют
    check_genres = f"""
        PREFIX fr: <{fr}>
        SELECT DISTINCT ?genreLabel (COUNT(?movie) as ?movieCount)
        WHERE {{
          ?movie a fr:Movie ;
                 fr:hasGenre ?genre .
          ?genre fr:label ?genreLabel .
        }}
        GROUP BY ?genreLabel
        ORDER BY DESC(?movieCount)
        LIMIT 10
    """
    execute_query(graph, check_genres, "Популярные жанры")

    # Проверяем данные за 2009 год
    check_2009 = f"""
        PREFIX fr: <{fr}>
        SELECT (COUNT(?movie) as ?movieCount)
        WHERE {{
          ?movie a fr:Movie ;
                 fr:releaseDate ?date .
          FILTER(YEAR(?date) = 2009)
        }}
    """
    execute_query(graph, check_2009, "Фильмы за 2009 год")


# Исправленные SPARQL-запросы
def sparql_queries(graph, fr):
    # Добавляем префиксы к запросам
    prefixes = f"""
        PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX fr:   <{fr}>
        PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
    """

    # 1. КАССОВЫЕ РЕЖИССЁРЫ
    query_1 = prefixes + """
        # 1. Кассовые режиссёры
        SELECT ?director ?directorName ?genreLabel
               (SUM(?revenue) AS ?totalRevenue)
               (COUNT(DISTINCT ?movie) AS ?movieCount)
        WHERE {
          ?movie a fr:Movie ;
                 fr:hasGenre ?genre ;
                 fr:revenue ?revenue ;
                 fr:releaseDate ?date ;
                 fr:hasCrew ?role .

          ?genre fr:label ?genreLabel .
          FILTER(CONTAINS(LCASE(?genreLabel), "action"))  # ищем жанры с этими словами

          BIND (YEAR(?date) AS ?year)
          FILTER (?year = 2009)

          ?role a fr:CrewRole ;
                fr:crewJob ?job ;
                fr:creditsPerson ?director .

          FILTER(CONTAINS(LCASE(?job), "director"))  # ищем любые director должности

          ?director fr:label ?directorName .
        }
        GROUP BY ?director ?directorName ?genreLabel
        ORDER BY DESC(?totalRevenue)
        LIMIT 10
    """
    execute_query(graph, query_1, "1. Кассовые режиссёры (2009 год, Action)")

    # 1а. Альтернатива: любой жанр за 2009 год
    query_1a = prefixes + """
        # 1а. Кассовые режиссёры за 2009 год (любой жанр)
        SELECT ?director ?directorName
               (SUM(?revenue) AS ?totalRevenue)
               (COUNT(DISTINCT ?movie) AS ?movieCount)
        WHERE {
          ?movie a fr:Movie ;
                 fr:revenue ?revenue ;
                 fr:releaseDate ?date ;
                 fr:hasCrew ?role .

          BIND (YEAR(?date) AS ?year)
          FILTER (?year = 2009)

          ?role a fr:CrewRole ;
                fr:crewJob ?job ;
                fr:creditsPerson ?director .

          FILTER(CONTAINS(LCASE(?job), "director"))

          ?director fr:label ?directorName .
        }
        GROUP BY ?director ?directorName
        ORDER BY DESC(?totalRevenue)
        LIMIT 10
    """
    execute_query(graph, query_1a, "1а. Кассовые режиссёры (2009 год, любой жанр)")

    # 2. АКТЁРЫ В ВЫСОКООЦЕНЁННЫХ ФИЛЬМАХ
    # Проблема: возможно, фильтры слишком строгие
    query_2 = prefixes + """
        # 2. Актёры в высокооценённых фильмах (более гибкие критерии)
        SELECT ?actor ?actorName ?genreLabel
               (COUNT(DISTINCT ?movie) AS ?highRatedMovieCount)
               (AVG(?rating) AS ?avgRating)
        WHERE {
          ?movie a fr:Movie ;
                 fr:hasGenre ?genre ;
                 fr:voteAverage ?rating ;
                 fr:releaseDate ?date ;
                 fr:hasCast ?castRole .

          ?genre fr:label ?genreLabel .
          FILTER(CONTAINS(LCASE(?genreLabel), "drama"))

          BIND (YEAR(?date) AS ?year)
          FILTER (?year >= 2000 && ?year <= 2010)
          FILTER (?rating >= 7.0)  # снизим порог

          ?castRole a fr:CastRole ;
                    fr:playedBy ?actor .

          ?actor fr:label ?actorName .
        }
        GROUP BY ?actor ?actorName ?genreLabel
        HAVING (COUNT(DISTINCT ?movie) >= 2)  # снизим до 2 фильмов
        ORDER BY DESC(?highRatedMovieCount) DESC(?avgRating)
        LIMIT 10
    """
    execute_query(graph, query_2, "2. Актёры в жанре Drama с высокими рейтингами (2000-2010)")

    # 3. КАССОВЫЕ КОМПАНИИ
    query_3 = prefixes + """
        # 3. Самые кассовые кино-компании
        SELECT ?company ?companyName
               (SUM(?revenue) AS ?totalRevenue)
               (COUNT(DISTINCT ?movie) AS ?movieCount)
        WHERE {
          ?movie a fr:Movie ;
                 fr:producedBy ?company ;
                 fr:revenue ?revenue ;
                 fr:releaseDate ?date .

          FILTER (?date >= "2005-01-01"^^xsd:date &&
                  ?date <= "2010-12-31"^^xsd:date)

          ?company fr:label ?companyName .
        }
        GROUP BY ?company ?companyName
        ORDER BY DESC(?totalRevenue)
        LIMIT 10
    """
    execute_query(graph, query_3, "3. Самые кассовые кино-компании (2005-2010)")

    # 4. ЯЗЫКИ С ВЫСОКИМИ РЕЙТИНГАМИ
    query_4 = prefixes + """
        # 4. Языки озвучки с высокими рейтингами в Sci-Fi
        SELECT ?lang ?langLabel
               (AVG(?rating) AS ?avgRating)
               (COUNT(DISTINCT ?movie) AS ?movieCount)
        WHERE {
          ?movie a fr:Movie ;
                 fr:hasGenre ?genre ;
                 fr:spokenLanguage ?lang ;
                 fr:voteAverage ?rating .
                 
          ?genre fr:label ?genreLabel .
          FILTER(CONTAINS(LCASE(?genreLabel), "science fiction"))
          
          # Пытаемся получить метку языка, если есть
          OPTIONAL { ?lang fr:label ?langLabel . }
          
          # Если нет метки, используем сам URI
          BIND(COALESCE(?langLabel, STR(?lang)) AS ?langLabel)
        }
        GROUP BY ?lang ?langLabel
        HAVING (COUNT(DISTINCT ?movie) >= 3)
        ORDER BY DESC(?avgRating)
        LIMIT 10
    """
    execute_query(graph, query_4, "4. Языки с высокими рейтингами в Sci-Fi")

    # 5. РЕЖИССЁРЫ С ОЦЕНКАМИ ВЫШЕ СРЕДНЕГО
    query_5_optimized = prefixes + """
        # 5. Режиссёры с оценками выше среднего по их жанрам (оптимизированный)
        SELECT ?director ?directorName ?genreName
               (AVG(?rating) AS ?directorAvgRating)
               ?genreAvgRating
               (COUNT(DISTINCT ?movie) AS ?directorMovieCount)
        WHERE {
          # Подзапрос: средний рейтинг по жанрам
          {
            SELECT ?genre (AVG(?r) AS ?genreAvgRating)
            WHERE {
              ?m a fr:Movie ;
                 fr:hasGenre ?genre ;
                 fr:voteAverage ?r .
              FILTER(?r > 0)
            }
            GROUP BY ?genre
            HAVING (COUNT(DISTINCT ?m) >= 10)
          }

          # Основной паттерн: фильмы × жанры × режиссёры
          ?movie a fr:Movie ;
                 fr:hasGenre ?genre ;
                 fr:voteAverage ?rating ;
                 fr:directedBy ?director .
          FILTER(?rating > 0)

          ?director fr:label ?directorName .
          ?genre    fr:label ?genreName .
        }
        GROUP BY ?director ?directorName ?genre ?genreName ?genreAvgRating
        HAVING (COUNT(DISTINCT ?movie) >= 2 &&
                AVG(?rating) > ?genreAvgRating)
        ORDER BY DESC(AVG(?rating) - ?genreAvgRating)
        LIMIT 50
    """

    execute_query(graph, query_5_optimized, "5. Режиссёры с самыми высокими средними рейтингами")

    # 6. СОТРУДНИКИ НА ВЫСОКОПРИБЫЛЬНЫХ ФИЛЬМАХ (оптимизированный)
    query_6 = prefixes + """
        # 6. Сотрудники на высокоприбыльных фильмах (через материализованный fr:profit)
        SELECT ?person ?personName
               (COUNT(DISTINCT ?movie) AS ?highProfitMovieCount)
        WHERE {

          # === (1) Один маленький подзапрос: средняя прибыль по фильмам ===
          {
            SELECT (AVG(?p) AS ?avgProfit)
            WHERE {
              ?m a fr:Movie ;
                 fr:profit ?p .
              FILTER(?p > 0)
            }
          }

          # === (2) Фильмы с прибылью выше средней ===
          ?movie a fr:Movie ;
                 fr:profit ?profit ;
                 fr:hasCrew ?crewRole .
          FILTER(?profit > ?avgProfit)

          # === (3) Участники съёмочной группы ===
          ?crewRole fr:creditsPerson ?person .
          ?person fr:label ?personName .
        }
        GROUP BY ?person ?personName
        HAVING (COUNT(DISTINCT ?movie) >= 2)
        ORDER BY DESC(?highProfitMovieCount)
        LIMIT 10
    """
    execute_query(graph, query_6, "6. Сотрудники на высокоприбыльных фильмах")

    # 7. ЖАНРЫ С ДЛИТЕЛЬНЫМИ ФИЛЬМАМИ
    query_7 = prefixes + """
        # 7. Жанры с самой большой продолжительностью фильмов
        SELECT ?genre ?genreName
               (AVG(?runtime) AS ?avgRuntime)
               (COUNT(DISTINCT ?movie) AS ?movieCount)
               (SUM(?revenue) AS ?totalRevenue)
        WHERE {
          ?movie a fr:Movie ;
                 fr:hasGenre ?genre ;
                 fr:runtime ?runtime ;
                 fr:revenue ?revenue ;
                 fr:releaseDate ?date .

          BIND (YEAR(?date) AS ?year)
          FILTER (?year = 2010)
          FILTER (?revenue >= 50000000)  # снизим порог успешности
          FILTER (?runtime > 0)  # исключаем нулевую продолжительность

          ?genre fr:label ?genreName .
        }
        GROUP BY ?genre ?genreName
        HAVING (COUNT(DISTINCT ?movie) >= 2)
        ORDER BY DESC(?avgRuntime)
        LIMIT 15
    """
    execute_query(graph, query_7, "7. Жанры с самой большой продолжительностью (2010)")

    # 8. КЛЮЧЕВЫЕ СЛОВА ЛУЧШИХ ФИЛЬМОВ
    query_8 = prefixes + """
        # 8. Ключевые слова лучших фильмов
        SELECT ?keyword ?keywordLabel
               (COUNT(DISTINCT ?movie) AS ?movieCount)
               (AVG(?rating) AS ?avgRating)
        WHERE {
          ?movie a fr:Movie ;
                 fr:hasKeyword ?keyword ;
                 fr:voteAverage ?rating ;
                 fr:releaseDate ?date .

          FILTER (?date >= "2000-01-01"^^xsd:date &&
                  ?date <= "2010-12-31"^^xsd:date)
          FILTER (?rating >= 7.0)  # снизим порог

          OPTIONAL { ?keyword fr:label ?keywordLabel . }
          FILTER(BOUND(?keywordLabel))  # только ключевые слова с меткой
        }
        GROUP BY ?keyword ?keywordLabel
        HAVING (COUNT(DISTINCT ?movie) >= 3)  # снизим порог
        ORDER BY DESC(?movieCount) DESC(?avgRating)
        LIMIT 10
    """
    execute_query(graph, query_8, "8. Ключевые слова лучших фильмов (2000-2010)")


# Главный скрипт
if __name__ == "__main__":

    try:
        print("Загрузка RDF графа...")
        graph = load_graph(RDF_FILE)

        # Настройка пространства имен
        fr = setup_namespace(graph)

        print(f"✓ Граф загружен успешно!")
        print(f"✓ Количество триплетов: {len(graph):,}")
        print(f"✓ Пространство имен: {fr}")

        # Проверка структуры данных
        check_data_structure(graph, fr)

        # Выполнение основных запросов
        print("\n" + "=" * 60)
        print("ВЫПОЛНЕНИЕ ОСНОВНЫХ ЗАПРОСОВ")
        print("=" * 60)

        # Выполняем запросы по одному с контролем времени
        sparql_queries(graph, fr)

        print("\n" + "=" * 60)
        print("ВЫПОЛНЕНИЕ ЗАВЕРШЕНО")
        print("=" * 60)

    except FileNotFoundError:
        print(f"✗ Ошибка: Файл '{RDF_FILE}' не найден.")
        print("  Укажите правильный путь к RDF файлу")
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback

        traceback.print_exc()