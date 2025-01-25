"""
 在此处定义所有需要使用的 multi-agent-debate 提示词模版
"""

FAIR_EVAL_DEBATE_TEMPLATE = """
[Context]
{source_text}
[System]
We would like to request your feedback on the "exactly matched database" which contains both sufficient and necessary schema(tables and columns) to perfectly answer the question above.
There are a few other referees assigned the same task, it’s your responsibility to discuss with them and think critically before you make your final judgment.
Do not blindly follow the opinions of other referees, as their insights may be flawed.
Here is your discussion history:
{chat_history}
{role_description}
# Please consider (1) whether the candidate database contains the required schema, (2) whether the schema contained in the candidate database can accurately generate SQL statements. 
# Please be aware that there is and only one database that exactly matches the user's question. Therefore, you need to ensure the accuracy of the selected database.Otherwise, it will lead to errors in the SQL statements.
Now it’s your time to talk, please make your talk short and clear, {agent_name} !
"""

DATABASE_SCIENTIST_ROLE_DESCRIPTION = """
You are database scientist,one of the referees in this debate.You are a seasoned professional with expertise in database theory, a thorough understanding of SQL specifications, and well-honed skills in critical thinking and problem-solving.
Your job is to to make sure the selected database by data analyst is well-considered and can be used to construct the exact SQL statements corresponding to the natural language question.
Please carefully observe the details and point out any shortcomings or errors in data analyst's answers
"""

DATA_ANALYST_ROLE_DESCRIPTION = """
You are data analyst, one of the referees in this debate.You are familiar with writing SQL statements and highly proficient in finding the most accurate database through rich intuition and experience.
You job is to determine the only one database which has the most sufficient data tables and data fields to construct the exact SQL statements corresponding to the question. 
"""

SOURCE_TEXT_TEMPLATE = """
The following is a user question in natural language form that requires discussion to determine the most appropriate database, capable of generating the corresponding SQL statement.
# question:{query}.
{context_str}
"""

SUMMARY_TEMPLATE = """
You are now a debate terminator, one of the referees in this task.
You job is to determine the most suitable database that represents the final outcome of the discussion.
#
Noted that strictly output one unique database name without any irrelevant content.
#
"""

LINKER_TEMPLATE = """
You are a database expert who is highly proficient in writing SQL statements. 
For a natural language question , you job is to identify and extract the correct database schemas(data tables and data fields) from database creation statements,
which is strictly necessary for writing the exact SQL statement in response to the question. 
#
Strictly output the results in a python list format:
[<data table name>.<data field name>...]
e.g. "movies" and "ratings" are two datatable in one database,then one possible output as following:
[movies.movie_release_year, movies.movie_title, ratings.rating_score]
#
{few_examples}
# The extraction work for this round officially begin now.
Database Table Creation Statements:
{context_str}
#
Question: {question}
Answer:
"""

SCHEMA_LINKING_FEW_EXAMPLES = """
### 
Here are a few reference examples that may help you complete this task. 
### 
Database Table Creation Statements:
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
Answer: [movies.movie_release_year, movies.movie_title, ratings.rating_score, movies.movie_id,ratings.movie_id]


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
Answer: [lists.list_followers,lists_users.user_subscriber,lists.user_id,lists_user.user_id,lists.list_id,lists_user.list_id]

###
"""

GENERATE_FAIR_EVAL_DEBATE_TEMPLATE = """
[Question]
{source_text}
[System]
We would like to request your feedback on the exactly correct database schemas(tables and columns),
which is strictly necessary for writing the right SQL statement in response to the user question displayed above.
There are a few other referees assigned the same task, it’s your responsibility to discuss with them and think critically and independantly before you make your final judgment.
Here is your discussion history:
{chat_history}
{role_description}
Please be mindful that failing to include any essential schemas, such as query columns or join table fields, can lead to erroneous SQL generation. 
Consequently, it is imperative to thoroughly review and double-check your extracted schemas to guarantee their completeness and ensure nothing is overlooked.
Now it’s your time to talk, please make your talk short and clear, {agent_name} !
"""

GENERATE_DATA_ANALYST_ROLE_DESCRIPTION = """
You are now data analyst, one of the referees in this task.You are highly proficient in writing SQL statements and independantly thinking.
Your job is to identify and extract all the necessary database schemas required for generating correct SQL statement that corresponds to the given problem.
"""

GENERATE_DATABASE_SCIENTIST_ROLE_DESCRIPTION = """
You are database scientist,one of the referees in this task.You are a professional engaged in SQL statement writing specifications, possessing a strong background in critical thinking,problem-solving abilities,and a robust capacity for independent thinking. 
Your primary responsibility is to guarantee that the extracted database schemas is adequately comprehensive, leaving no room for omitting any essential tables or columns.
Please help data analysts identify any errors or deficiencies in the extracted database schemas from data analysts (e.g. redundant or noisy fields, missing key query entities, missing critical filtering conditions, without crucial database join fields, etc.).
Noted that disregard the shortcomings in the database table creation statements.
"""
# line 2:Your job is to to ensure that the selected database schemas are well-considered and can be used to construct the exact SQL statements corresponding to the Natural Language Question.

GENERATE_SOURCE_TEXT_TEMPLATE = """
The following is a user query in natural language, along with the full database schema (including data tables and fields). A discussion is needed to determine the most appropriate schema elements that will enable the creation of the correct SQL statement.
## 
query:{query}
##
{context_str}
l
"""

GENERATE_SUMMARY_TEMPLATE = """
You are now a debate terminator, one of the referees in this task. 
You job is to filter all of the necessary database schemas(tables and columns) that represents the final outcome of the discussion.
#
Noted that strictly output the database schemas in a python List format:
[<data table name>.<data field name>...]
e.g. "movies" and "ratings" are two datatable in one database,then one possible output as following:
[movies.movie_release_year, movies.movie_title, ratings.rating_score]
#
"""

# Do not omit any database schemas proposed during the discussion.
