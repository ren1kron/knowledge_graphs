Перед запросами, возможно, нужно добавить:
```sparql
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX fr:   <http://example.org/film-rating#>
```

# Графы знаний: компетентносные вопросы

1) Какие режиссёры в конкретном жанре были кассовыми в конкретном году?
```sparql
SELECT ?director ?directorName
       (SUM(?revenue) AS ?totalRevenue)
       (COUNT(DISTINCT ?movie) AS ?movieCount)
WHERE {
  ?movie a fr:Movie ;
         fr:hasGenre ?genre ;
         fr:revenue ?revenue ;
         fr:releaseDate ?date ;
         fr:hasCrew ?role .

  ?genre fr:label "Action" .          # тут жанр
  BIND (YEAR(?date) AS ?year)
  FILTER (?year = 2009)               # тут год

  ?role a fr:CrewRole ;
        fr:crewJob "Director" ;       # режиссёры
        fr:creditsPerson ?director .

  ?director fr:label ?directorName .
}
GROUP BY ?director ?directorName
ORDER BY DESC(?totalRevenue)
LIMIT 20
```
2) Какие актёры в заданном жанре регулярно появлялись в высокооценённых фильмах в течение определённого промежутка времени?
```sparql
SELECT ?actor ?actorName
       (COUNT(DISTINCT ?movie) AS ?highRatedMovieCount)
WHERE {
  ?movie a fr:Movie ;
         fr:hasGenre ?genre ;
         fr:voteAverage ?rating ;
         fr:releaseDate ?date ;
         fr:hasCast ?castRole .

  ?genre fr:label "Drama" .          # жанр
  BIND (YEAR(?date) AS ?year)
  FILTER (?year >= 2000 && ?year <= 2010)  # промежуток времени
  FILTER (?rating >= 7.5)                  # "высоко оценённый" фильм

  ?castRole a fr:CastRole ;
            fr:playedBy ?actor .

  ?actor fr:label ?actorName .
}
GROUP BY ?actor ?actorName
HAVING (COUNT(DISTINCT ?movie) >= 3)       # "регулярно" = минимум 3 фильма
ORDER BY DESC(?highRatedMovieCount) ?actorName
LIMIT 50
```
3) Какие кино-компании спродюссировали самые кассовые фильмы в конкретный промежуток времени?
```sparql
SELECT ?company ?companyName
       (SUM(?revenue) AS ?totalRevenue)
       (COUNT(DISTINCT ?movie) AS ?movieCount)
WHERE {
  ?movie a fr:Movie ;
         fr:producedBy ?company ;
         fr:revenue ?revenue ;
         fr:releaseDate ?date .

  FILTER (?date >= "2005-01-01"^^xsd:date &&
          ?date <= "2010-12-31"^^xsd:date)  # период

  ?company fr:label ?companyName .
}
GROUP BY ?company ?companyName
ORDER BY DESC(?totalRevenue)
LIMIT 20

```
4) Какой язык оригинальной озвучки ассоциирован с наиболее высокими средними рейтингами фильмов в конкретном жанре?
```sparql
SELECT ?lang ?langLabel
       (AVG(?rating) AS ?avgRating)
       (COUNT(DISTINCT ?movie) AS ?movieCount)
WHERE {
  ?movie a fr:Movie ;
         fr:hasGenre ?genre ;
         fr:originalLanguage ?lang ;
         fr:voteAverage ?rating .

  ?genre fr:label "Science Fiction" .        # жанр

  OPTIONAL { ?lang fr:label ?langLabel . }
}
GROUP BY ?lang ?langLabel
HAVING (COUNT(DISTINCT ?movie) >= 5)         # можно отсеять языки с 1 фильмом
ORDER BY DESC(?avgRating)
LIMIT 10

```
5) Какие режиссёры снимают фильмы с более высокими оценками чем в среднем по жанру
```sparql
SELECT ?director ?directorName
       ?genre ?genreName
       ?directorAvgRating ?genreAvgRating
WHERE {
  # Подзапрос: средний рейтинг по жанру
  {
    SELECT ?genre (AVG(?r) AS ?genreAvgRating)
    WHERE {
      ?m a fr:Movie ;
         fr:hasGenre ?genre ;
         fr:voteAverage ?r .
    }
    GROUP BY ?genre
  }

  # Подзапрос: средний рейтинг режиссёра в жанре
  {
    SELECT ?director ?genre (AVG(?r2) AS ?directorAvgRating)
    WHERE {
      ?movie a fr:Movie ;
             fr:hasGenre ?genre ;
             fr:voteAverage ?r2 ;
             fr:hasCrew ?role .

      ?role a fr:CrewRole ;
            fr:crewJob "Director" ;
            fr:creditsPerson ?director .
    }
    GROUP BY ?director ?genre
    HAVING (COUNT(DISTINCT ?movie) >= 2)      # режиссёр снял >= 2 фильмов в жанре
  }

  ?director fr:label ?directorName .
  ?genre    fr:label ?genreName .

  FILTER (?directorAvgRating > ?genreAvgRating)
}
ORDER BY DESC(?directorAvgRating)
LIMIT 50

```
6) Какой съёмочный каст чаще всего работает над фильмами с профитностью выше средней?
```sparql
SELECT ?person ?personName
       (COUNT(DISTINCT ?movie) AS ?highProfitMovieCount)
WHERE {

  # Подзапрос: средний профит по фильмам
  {
    SELECT (AVG(?profit) AS ?avgProfit)
    WHERE {
      ?m a fr:Movie ;
         fr:revenue ?rev ;
         fr:budget ?bud .
      BIND (xsd:decimal(?rev - ?bud) AS ?profit)
    }
  }

  # Фильмы с профитом выше среднего
  ?movie a fr:Movie ;
         fr:revenue ?revenue ;
         fr:budget ?budget ;
         fr:hasCrew ?crewRole .

  BIND (xsd:decimal(?revenue - ?budget) AS ?profitMovie)
  FILTER (?profitMovie > ?avgProfit)

  ?crewRole a fr:CrewRole ;
            fr:creditsPerson ?person .

  ?person fr:label ?personName .
}
GROUP BY ?person ?personName
HAVING (COUNT(DISTINCT ?movie) >= 3)
ORDER BY DESC(?highProfitMovieCount)
LIMIT 50
```
7) Какие жанры, как правило, имеют более длительную продолжительность у коммерчески успешных фильмов, вышедших в определённом году?
```sparql
SELECT ?genre ?genreName
       (AVG(?runtime) AS ?avgRuntime)
       (COUNT(DISTINCT ?movie) AS ?movieCount)
WHERE {
  ?movie a fr:Movie ;
         fr:hasGenre ?genre ;
         fr:runtime ?runtime ;
         fr:revenue ?revenue ;
         fr:releaseDate ?date .

  BIND (YEAR(?date) AS ?year)
  FILTER (?year = 2010)                # год

  FILTER (?revenue >= 100000000)       # "коммерчески успешный" порог

  ?genre fr:label ?genreName .
}
GROUP BY ?genre ?genreName
HAVING (COUNT(DISTINCT ?movie) >= 3)
ORDER BY DESC(?avgRuntime)
LIMIT 20

```
8) Какие ключевые слова наиболее ассоциированы с лучшими по рейтингу фильмами в конкретный промежуток времени?
```sparql
SELECT ?keyword ?keywordLabel
       (COUNT(DISTINCT ?movie) AS ?movieCount)
       (AVG(?rating) AS ?avgRating)
WHERE {
  ?movie a fr:Movie ;
         fr:hasKeyword ?keyword ;
         fr:voteAverage ?rating ;
         fr:releaseDate ?date .

  FILTER (?date >= "2000-01-01"^^xsd:date &&
          ?date <= "2010-12-31"^^xsd:date)  # период

  FILTER (?rating >= 7.5)                    # "лучшие" фильмы

  OPTIONAL { ?keyword fr:label ?keywordLabel . }
}
GROUP BY ?keyword ?keywordLabel
HAVING (COUNT(DISTINCT ?movie) >= 5)
ORDER BY DESC(?movieCount) DESC(?avgRating)
LIMIT 50

```