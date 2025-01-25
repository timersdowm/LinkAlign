# DIN-SQL schema linking 提示词
DIN_SCHEMA_LINKING_TEMPLATE = """
You are a database expert who is highly proficient in writing SQL statements. 
For a natural language question , you job is to identify and extract the correct data tables and data fields from database creation statements,
which is strictly necessary for the accurate SQL statement corresponding to the question. 
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
Only output a Python json object as your answer without any irrelevant contents:
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

MAC_SCHEMA_LINKING_TEMPLATE = """
# Task Description
### As an experienced and professional database administrator , your task is to ...
# Instruction
### 1. Discard any table schema that is not related to the user question and evidence .
### 2. Sort the columns in each relevant table in descending order of relevance and keep the top 6 columns .
### 3. Ensure that at least 3 tables are included in the final output List .
### 4. TStrictly output the results in a python list format: [<data table name>.<data field name>...] .
# Demonstration
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
Answer: [movies.movie_release_year, movies.movie_title, ratings.rating_score, movies.movie_id,ratings.movie_id]
###
# Test Question
### {context}
### question: {question}
### Only output a Python List object as your response without any irrelevant contents:
"""

# MCS-SQL
MCS_TABLE_LINKING_TEMPLATE = """
### Given a database schema, question, and knowledge evidence, extract a list of
tables that should be referenced to convert the question into SQL.
### SQLite SQL tables, with their properties:
{context}
### Question: {question}.
You need to not only select the required tables, but also explain in detail why each table is needed.
###
Your answer should strictly follow the following json format.
{{
"reasoning": "", // The reason for choosing each table.
"tables": [], // List of selected tables.
}}
### 
Only output a Python json object as your response without any irrelevant contents:
"""

MCS_COLUMN_LINKING_TEMPLATE = """
### Given a database schema, question, and knowledge evidence, extract a list of columns that should be referenced to convert the question into SQL.
### SQLite SQL tables, with their properties:
{context}
### Question: {question}
You need to not only select the required columns, but also explain in detail why each column is needed.
### 
Your answer should strictly follow the following json format.
{{
"reasoning": "", // The reason for choosing each column.
"columns": ["table_name_i.column_name_j", ...], // List of selected columns
}}
### 
Strictly output a json as your response without any irrelevant contents:
"""

# CHESS
CHESS_FILTER_COLUMN_TEMPLATE = """
You are a detail-oriented data scientist tasked with evaluating the relevance of database column information for answering specific SQL query question based on provided hint.

Your goal is to assess whether the given column details are pertinent to constructing an SQL query to address the question informed by the hint. Label the column information as "relevant" if it aids in query formulation, or "irrelevant" if it does not.

Procedure:
1. Carefully examine the provided column details.
2. Understand the question about the database and its associated hint.
3. Decide if the column details are necessary for the SQL query based on your analysis.

Here are some examples of how to determine if the column information is relevant or irrelevant to the question and the hint:

Example 1:
Column information:
Table name: `movies`
Original column name: `movie_title`
Data type: TEXT
Description: Name of the movie
Example of values in the column: `La Antena`


Question:
Name movie titles released in year 1945. Sort the listing by the descending order of movie popularity.

HINT:
released in the year 1945 refers to movie_release_year = 1945;

```json
{{
  "chain_of_thought_reasoning": "The question specifically asks for movie titles from a particular year and to sort them by popularity. The column movie_title directly provides the names of movies, which is exactly what is required to list the movie titles as requested in the question.",
  "is_column_information_relevant": "Yes"
}}
```

Example 2:
Column information:
Table name: `movies`
Original column name: `movie_release_year`
Data type: INTEGER
Description: Release year of the movie
Example of values in the column: `2007`


Question:
List all movie title rated in April 2020 from user who was a trialist.

HINT:
movie title rated in April 2020 refers to rating_timestamp_utc LIKE '%2020-04-%'; user is a trial list refers to user_trialist = 1;

```json
{{
  "chain_of_thought_reasoning": "The question and hint focus on movies rated in a specific month and year and by a specific type of user (trialist), neither of which relates to the movie_release_year column. This column only provides the year movies were released, which is not what is being queried.",
  "is_column_information_relevant": "No"
}}
```

Example 3:
Column information:
Table name: `ratings_users`
Original column name: `user_has_payment_method`
Data type: INTEGER
Description: whether the user was a paying subscriber when he rated the movie
Value description: 1 = the user was a paying subscriber when he rated the movie  0 = the user was not a paying subscriber when he rated
Example of values in the column: `0`


Question:
How many users, who were a paying subscriber when they rated the movie, gave the movie that was released in 1924 and directed by Erich von Stroheim a rating score of 5?

HINT:
Directed by Buster Keaton refers to director_name; released in 1924 refers to movie_release_year = 1924; paying subscriber refers to user_has_payment_method = 1; rating score of 5 refers to rating_score = 5;

```json
{{
  "chain_of_thought_reasoning": "The question asks about users who were paying subscribers and rated a specific movie from 1924 directed by a specific director. The user_has_payment_method column indicates whether a user was a paying subscriber at the time of rating, which is directly relevant to the question and the hint focusing on subscribers.",
  "is_column_information_relevant": "Yes"
}}
```

Example 4:
Column information:
Table name: `movies`
Original column name: `director_name`
Data type: TEXT
Description: Full Name of the movie director
Example of values in the column: `Stanley Kubrick`


Question:
What is the average number of Mubi users who love movies directed by Stanley Kubrick?

HINT:
average = AVG(movie_popularity); number of Mubi users who loves the movie refers to movie_popularity;

```json
{{
  "chain_of_thought_reasoning": "The question requires filtering movies directed by `Stanley Kubrick` to calculate the average popularity. The director_name column provides the director's name, and as shown in the example values, it includes `Stanley Kubrick`, which is essential for filtering movies directed by this specific director.",
  "is_column_information_relevant": "Yes"
}}
```

Now, its your turn to determine whether the provided column information can help formulate a SQL query to answer the given question, based on the provided hint.

The following guidelines are VERY IMPORTANT to follow. Make sure to check each of them carefully before making your decision:
1. You're given only one column's information, which alone isn't enough to answer the full query. Concentrate solely on this provided data and assess its relevance to the question and hint without considering any missing information.
2. Read the column information carefully and understand the description of it, then see if the question or the hint is asking or referring to the same information. If yes then the column information is relevant, otherwise it is irrelevant.
3. Look beyond mere keywords. Assess whether there is a meaningful, semantic connection between the column information and the needs of the question or hint. Mere word matches do not necessarily imply relevance.
4. If the question refers to applying a logic on a data such as average, sum, max, min, or any other operation, and the column information is a part of that logic, then the column information is relevant.
5. Pay attention to the provided `Example of values in the column`. If you see a shared keyword between the example and the question or hint, then the column information is relevant. (VERY IMPORTANT)
6. If you see the column name appeared in the hint, then it is definitely relevant. (VERY IMPORTANT)
7. Note that it does not matter if the question is asking for other information not contained in the column, as long as this column's information is useful for crafting a SQL query answering the question, you should consider this column as relevant.

Column information:
{COLUMN_PROFILE}

Question:
{QUESTION}

Take a deep breath and provide your answer in the following json format:

```json
{{
  "chain_of_thought_reasoning": "One line explanation of why or why not the column information is relevant to the question and the hint.",
  "is_column_information_relevant": "Yes" or "No"
}}
```

Only output a json as your response.
"""

CHESS_SELECT_TABLE_TEMPLATE = """
You are an expert and very smart data analyst. 
Your task is to analyze the provided database schema, comprehend the posed question, and leverage the hint to identify which tables are needed to generate a SQL query for answering the question.

Database Schema Overview:
{DATABASE_SCHEMA}

This schema provides a detailed definition of the database's structure, including tables, their columns, primary keys, foreign keys, and any relevant details about relationships or constraints.
For key phrases mentioned in the question, we have provided the most similar values within the columns denoted by "-- examples" in front of the corresponding column names. This is a critical hint to identify the tables that will be used in the SQL query.

Question:
{QUESTION}

Task:
Based on the database schema, question, and hint provided, your task is to determine the tables that should be used in the SQL query formulation. 
For each of the selected tables, explain why exactly it is necessary for answering the question. Your explanation should be logical and concise, demonstrating a clear understanding of the database schema, the question, and the hint.

Please respond with a JSON object structured as follows:

```json
{{
  "chain_of_thought_reasoning": "Explanation of the logical analysis that led to the selection of the tables.",
  "table_names": ["Table1", "Table2", "Table3", ...]
}}
```

Note that you should choose all and only the tables that are necessary to write a SQL query that answers the question effectively.
Take a deep breath and think logically. If you do the task correctly, I will give you 1 million dollars. 

Only output a json as your response.
"""

CHESS_SELECT_COLUMN_TEMPLATE = """
You are an expert and very smart data analyst.
Your task is to examine the provided database schema, understand the posed question, and use the hint to pinpoint the specific columns within tables that are essential for crafting a SQL query to answer the question.

Database Schema Overview:
{DATABASE_SCHEMA}

This schema offers an in-depth description of the database's architecture, detailing tables, columns, primary keys, foreign keys, and any pertinent information regarding relationships or constraints. Special attention should be given to the examples listed beside each column, as they directly hint at which columns are relevant to our query.

For key phrases mentioned in the question, we have provided the most similar values within the columns denoted by "-- examples" in front of the corresponding column names. This is a critical hint to identify the columns that will be used in the SQL query.

Question:
{QUESTION}

Task:
Based on the database schema, question, and hint provided, your task is to identify all and only the columns that are essential for crafting a SQL query to answer the question.
For each of the selected columns, explain why exactly it is necessary for answering the question. Your reasoning should be concise and clear, demonstrating a logical connection between the columns and the question asked.

Tip: If you are choosing a column for filtering a value within that column, make sure that column has the value as an example.


Please respond with a JSON object structured as follows:
```json
{{
  "chain_of_thought_reasoning": "Your reasoning for selecting the columns, be concise and clear.",
  "table_name1": ["column1", "column2", ...],
  "table_name2": ["column1", "column2", ...],
  ...
}}
```

Make sure your response includes the table names as keys, each associated with a list of column names that are necessary for writing a SQL query to answer the question.
For each aspect of the question, provide a clear and concise explanation of your reasoning behind selecting the columns.
Take a deep breath and think logically. If you do the task correctly, I will give you 1 million dollars.

Only output a json as your response.
"""

# C3
C3_TABLE_RECALL_TEMPLATE = """
Given the database schema and question, perform the following actions:
1 - Rank all the tables based on the possibility of being used in the SQL according to the question from
the most relevant to the least relevant, Table or its column that matches more with the question words is
highly relevant and must be placed ahead.
2 - Check whether you consider all the tables.
3 - Output a list object in the order of step 2, Your output should contain all the tables. The format should
be like:
["table_1", "table_2", ...]
Schema:
{context}
Question:
### {question}
# Only output a list as your response.
"""

C3_COLUMN_RECALL_TEMPLATE = """
Given the database tables and question, perform the following actions:
1 - Rank the columns in each table based on the possibility of being used in the SQL, Column that
matches more with the question words or the foreign key is highly relevant and must be placed ahead.
You should output them in the order of the most relevant to the least relevant.
Explain why you choose each column.
2 - Output a List object that contains all the columns in each table according to your explanation. The

Strictly output the results in a python list format:
[<data table name>.<data field name>...]
e.g. "movies" and "ratings" are two datatable in one database,then one possible output as following:
[movies.movie_release_year, movies.movie_title, ratings.rating_score]
#
Schema:
{context}
Question:
### {question}
# Only output a list as your response without any irrelevant content.
"""

# Pet
PET_GENERATE_PRE_SQL_TEMPLATE = """
### Some example pairs of question and corresponding SQL query are provided based on similar problems:
{{context_str}}
### Answer the question by sqlite SQL query only and with no explanation. You must minimize SQL execution time while ensuring correctness.
### Sqlite SQL tables, with their properties:
#
{schema}
#
### Question: {question}
### SQL(strictly output a sql statement without any irrelevant content): 
"""

# RSL
RSL_TABLE_COLUMN_SELECTION_TEMPLATE = """
You are an intelligent agent responsible for identifying the database tables involved based on the user's questions and database structure information. Your main tasks are:

1. Understand user questions: parse user questions and extract keywords and intentions.
2. Obtain database structure information: Based on the provided database structure information, understand all tables and their relationships.
3. Identify relevant tables:
   - Based on the keywords and intentions in the user's questions, identify directly related tables.
   - Consider the situation of intermediate tables, such as connection tables or cross tables, which may involve the tables in the user's questions.
4. Generate a list of tables: Integrate directly related tables and intermediate tables to form the final list of tables.
5. Return the results in json format, the format is {{"tables": ["table1", "table2", ...],"columns":["table1.`column1`","table2.`column2`",...]}}

### Input:
- Database structure information: including table names, fields, and relationships between tables (such as foreign keys, etc.).
- User questions: queries or questions in natural language form.

### Output:
- List of database tables involved: including directly related tables and intermediate tables.

### Operation steps:
1. Parse user questions: extract keywords and intentions from the questions.
2. Identify key tables: preliminarily identify the direct tables related to the user's questions.
3. Check intermediate tables: Based on the database structure information, identify intermediate tables related to the direct tables.
4. Integrate the results: integrate direct tables and intermediate tables to form the final list of tables.
5. Output the results: return all table lists involved in the user's questions. Select the top 15 columns most relevant to the question for each table.

### Note:
- Ensure that all possible intermediate tables are considered, especially tables involving many-to-many relationships.
- Ensure that the output table list is unique and without duplicates.

### Here are all the table creation statements for the SQLite database, including tables, their properties, data information, and foreign key details for table joins.
{schema}
### Question: {question}
### Only output a json as your response.
"""

RSL_SQL_GENERATION_INSTRUCTION = '''
You are a smart agent responsible for generating the correct SQL statements based on the following information:
- A small number of SQL Q&A pairs: used for reference and learning common query patterns.
- Database structure information: including table names, fields, relationships between tables (such as foreign keys, etc.).
- The first three rows of values in the table: sample data for understanding the content and data distribution of the table.
- User questions: natural language queries or questions.
- Query requirements and conditions: specific query requirements and conditions in user questions.
- Tables involved in SQL statements: tables involved in user questions.
- Auxiliary query conditions: additional query conditions provided, which may affect the generation of SQL statements.
- definition: Information for prompts, this message is very important.

Your main tasks are:

1. Parse user questions:
   - Use natural language processing (NLP) techniques to parse user questions and extract query requirements and conditions.

2. Refer to SQL Q&A pairs:
    - Use the provided SQL Q&A pairs as a reference to understand common query patterns and SQL statement structures.

3. Analyze database structure information:
    - Based on the database structure information, understand the fields and relationships of the table, and build the basic framework of the SQL statement.

4. Check sample data:
    - Analyze the data characteristics based on the first three rows of the table, which helps to determine how to construct query conditions and filter results.

5. Generate SQL statements:
    - Based on user questions, query requirements and conditions, tables involved, and auxiliary query conditions, construct complete SQL statements.

6. Verification and optimization:
    - Check whether the generated SQL statement is logical and optimize it if necessary.

### Input:
- SQL Q&A pairs: a small number of example SQL Q&A pairs.
- Database structure information: including table names, fields, relationships between tables (such as foreign keys, etc.).
- The first three rows of values in the table: sample data.
- User questions: natural language queries or questions.
- Query requirements and conditions: specific query requirements and conditions in user questions.
- Tables involved in SQL statements: tables involved in user questions.
- Auxiliary query conditions: additional query conditions.
- definition: Information for prompts, this message is very important.

### Output:
- Return the result in json format, the format is {"sql": "SQL statement that meets the user's question requirements"}

### Operation steps:
1. Parse user questions: extract query requirements and conditions from the questions.
2. Refer to SQL Q&A pairs: understand common query patterns and SQL statement structures.
3. Analyze database structure information: build the basic framework of the SQL statement.
4. Check sample data: determine query conditions and filter results.
5. Generate SQL statements: construct complete SQL statements.
6. Verification and optimization: ensure the logical correctness of the SQL statement and optimize it.

### Note:
- Ensure that the SQL statement accurately reflects the query requirements and conditions in the user questions.
- Reasonably construct query logic based on database structure and sample data.
- When generating SQL statements, consider all the information provided to ensure the correctness and efficiency of the statements.
- If the user question involves complex query requirements, please consider all requirements and conditions to generate SQL statements.

### The most important thing is to remember:
- definition: Information for prompts, this message is very important.
- In the generated SQL statement, table names and field names need to be enclosed in backticks, such as `table_name`, `column_name`.
- In the generated SQL statement, table names and field names must be correct to ensure the correctness and efficiency of the statement.
'''