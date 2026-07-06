Create a Dataiku Python code that takes a DSS projectKey as an input, and returns a variety of facts about that dataset as a dict. If a field throws an exception or returns None, then return None. It is for Dataiku DSS v14.7.0.

This code is a preliminary pass at quantifying the quality of DSS projects. It will be used to analyze them compared to human labeled quality of projects. This code will output a collection of relevant fields that will be used to compute further information.

Include:
- projectKey
- project short description
- project long description
- project status
- number of tags
- starCount from get_interest
- watchCount from get_interest
- and the number of each of the following in this project:
  - continuous activities
  - unique contributors (users), get from the git log
  - age in days from today since createdBy
  - count of unique datasets, including shared ones
  - streaming endpoints
  - ML tasks
  - analyses from list_analyses()
  - saved models
  - model evaluation stores
  - evaluation stores
  - model_comparisons
  - jobs
  - API services
  - exported bundles
  - scenarios
  - total recipes
  - flow zones
  - object discussions
  - code studios
  - LLMs
  - knowledge banks
  - retrieval augmented llms
  - semantic models
  - agents
  - agent tools
  - web apps
  - dashboards
  - insights
  - number of wiki articles
  - number of commits in the project's git repository
  - tags assigned to the project
- calculated fields:
  - age in days from today since the project was last modified
  - age in days from today since the project last had a successful job run. Return None if there are none
  - percentage of all jobs that were successful without errors (warnings are okay)
  - sum total all notebooks from list_jupyter_notebooks, list_sql_notebooks
