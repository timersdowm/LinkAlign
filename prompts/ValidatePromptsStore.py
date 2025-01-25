VALIDATE_SCHEMA_LINKING_TEMPLATE = """
You are a database expert who is highly proficient in writing SQL statements. 
For a question presented in natural language, you need to perform semantic analysis to identify and extract the tables and column names required to construct the SQL statement. 
#
Strictly output the results in a python tuple format:
([<data table name>.<data field name>...],'<database name>')
e.g. 
if database name is 'movies',one possible output is as following:
output:[movies.movie_release_year, movies.movie_title, ratings.rating_score, movies.movie_id,ratings.movie_id],'<movies>')
#
{few_examples}
# The extraction work for this round officially begin now.
Database Table Creation Statements:
{context_str}
#
Question: {question}
Answer(Strictly output a python tuple object without any irrelevant content):
"""

VALIDATE_SCHEMA_LINKING_FEW_EXAMPLES = """
### 
Here are a few reference examples that may help you complete this task. 
### 
Database Table Creation Statements:
#
### 
Database Name: movies
#
Following is the whole table creation statement for the database popular_movies
CREATE TABLE movies (
        movie_id INTEGER NOT NULL, 
        movie_title TEXT, 
        movie_release_year INTEGER, 
        movie_url TEXT, 
        movie_title_language TEXT, 
        movie_popularity INTEGER, 
        movie_image_url TEXT, 
        director_id TEXT, 
        director_name TEXT, 
        director_url TEXT, 
        PRIMARY KEY (movie_id)
)
CREATE TABLE ratings (
        movie_id INTEGER, 
        rating_id INTEGER, 
        rating_url TEXT, 
        rating_score INTEGER, 
        rating_timestamp_utc TEXT, 
        critic TEXT, 
        critic_likes INTEGER, 
        critic_comments INTEGER, 
        user_id INTEGER, 
        user_trialist INTEGER, 
        user_subscriber INTEGER, 
        user_eligible_for_trial INTEGER, 
        user_has_payment_method INTEGER, 
        FOREIGN KEY(movie_id) REFERENCES movies (movie_id), 
        FOREIGN KEY(user_id) REFERENCES lists_users (user_id), 
        FOREIGN KEY(rating_id) REFERENCES ratings (rating_id), 
        FOREIGN KEY(user_id) REFERENCES ratings_users (user_id)
)
Question: Which year has the least number of movies that was released and what is the title of the movie in that year that has the highest number of rating score of 1?
Hint: least number of movies refers to MIN(movie_release_year); highest rating score refers to MAX(SUM(movie_id) where rating_score = '1')
Analysis: Let’s think step by step. In the question , we are asked:
"Which year" so we need column = [movies.movie_release_year]
"number of movies" so we need column = [movies.movie_id]
"title of the movie" so we need column = [movies.movie_title]
"rating score" so we need column = [ratings.rating_score]
Hint also refers to the columns = [movies.movie_release_year, movies.movie_id, ratings.rating_score]
Based on the columns and tables, we need these Foreign_keys = [movies.movie_id = ratings.movie_id].
Based on the tables, columns, and Foreign_keys, The set of possible cell values are = [1]. So the Schema_links are:
Answer: ([movies.movie_release_year, movies.movie_title, ratings.rating_score, movies.movie_id,ratings.movie_id],'<popular_movies>')


#
Following is the whole table creation statement for the database user_list
CREATE TABLE lists (
        user_id INTEGER, 
        list_id INTEGER NOT NULL, 
        list_title TEXT, 
        list_movie_number INTEGER, 
        list_update_timestamp_utc TEXT, 
        list_creation_timestamp_utc TEXT, 
        list_followers INTEGER, 
        list_url TEXT, 
        list_comments INTEGER, 
        list_description TEXT, 
        list_cover_image_url TEXT, 
        list_first_image_url TEXT, 
        list_second_image_url TEXT, 
        list_third_image_url TEXT, 
        PRIMARY KEY (list_id), 
        FOREIGN KEY(user_id) REFERENCES lists_users (user_id)
)
CREATE TABLE lists_users (
        user_id INTEGER NOT NULL, 
        list_id INTEGER NOT NULL, 
        list_update_date_utc TEXT, 
        list_creation_date_utc TEXT, 
        user_trialist INTEGER, 
        user_subscriber INTEGER, 
        user_avatar_image_url TEXT, 
        user_cover_image_url TEXT, 
        user_eligible_for_trial TEXT, 
        user_has_payment_method TEXT, 
        PRIMARY KEY (user_id, list_id), 
        FOREIGN KEY(list_id) REFERENCES lists (list_id), 
        FOREIGN KEY(user_id) REFERENCES lists (user_id)
)
Question: Among the lists created by user 4208563, which one has the highest number of followers? Indicate how many followers it has and whether the user was a subscriber or not when he created the list.
Hint: User 4208563 refers to user_id;highest number of followers refers to MAX(list_followers); user_subscriber = 1 means that the user was a subscriber when he created the list; user_subscriber = 0 means the user was not a subscriber when he created the list (to replace)
Analysis: Let’s think step by step. In the question , we are asked:
"user" so we need column = [lists_users.user_id]
"number of followers" so we need column = [lists.list_followers]
"user was a subscriber or not" so we need column = [lists_users.user_subscriber]
Hint also refers to the columns = [lists_users.user_id,lists.list_followers,lists_users.user_subscriber]
Based on the columns and tables, we need these Foreign_keys = [lists.user_id = lists_user.user_id,lists.list_id = lists_user.list_id].
Based on the tables, columns, and Foreign_keys, The set of possible cell values are = [1, 4208563]. So the Schema_links are:
Answer: ([lists.list_followers,lists_users.user_subscriber,lists.user_id,lists_user.user_id,lists.list_id,lists_user.list_id],'<user_list>')

###
"""
