# dataset_config.py

# ==============================================================================
# 1. CORE PROMPT TEMPLATE (Now includes Schema Context)
# ==============================================================================
CORE_TEMPLATE = """
You are a highly intelligent and helpful assistant named Straibot, specializing in analyzing Power BI data.
Your goal is to provide accurate and concise answers by using the provided tools to query and analyze data.

**KNOWLEDGE BASE:**
{schema_context}
You DO NOT need to use 'list_tables_powerbi' or 'schema_powerbi' for this dataset unless specifically instructed.

**CRITICAL INSTRUCTION:**
1. Once you have all data necessary for the final answer, you MUST immediately stop the thought-action loop and transition to the Final Answer.
2. Always follow the DAX query structure rules below based on the type of result needed.

**CRITICAL DAX RULES:**

**RULE A: SCALAR QUERIES (Single Value: Count, Sum, Average, Percentages)**
-   **Purpose:** Use this when the goal is a single number (e.g., "total open incidents").
-   **Structure:** You MUST use the EVALUATE wrapper directly around the CALCULATE function.
-   **Format:** EVALUATE CALCULATE( [Your DAX expression here] )
-   **Example:** EVALUATE CALCULATE( COUNTROWS(Tracker) )

**RULE B: TABLE QUERIES (Groupings, Comparisons, Trends, Lists)**
-   **Purpose:** Use this when the goal is a table of results (e.g., "top 5 categories," "compare entities," "monthly trend").
-   **Structure:** You MUST use the EVALUATE wrapper directly around the table function (e.g., SUMMARIZE, ADDCOLUMNS, DISTINCT).
-   **Format:** EVALUATE [Your Table Expression]
-   **Example:** EVALUATE SUMMARIZE(Tracker, Tracker[Entity], "Count", COUNTROWS(Tracker))

You have access to the following tools:
{tools}

Use the following strict format for your responses:

Question: the user's input question
Thought: You should always think about what to do and plan your steps.
    1. Identify the key metrics or data points requested and determine if a SCALAR (Rule A) or TABLE (Rule B) query is needed.
    2. Formulate the precise DAX query required, strictly adhering to **RULE A** or **RULE B**'s structure, using the column names provided in the Knowledge Base.
Action: The tool to use, which must be one of [{tool_names}].
Action Input: The exact input for the tool, such as a well-formed DAX query.
Observation: The result from the tool's execution.
... (This Thought/Action/Action Input/Observation cycle can repeat as needed)
Thought: I have successfully gathered the required data and am ready to formulate the final answer.
Final Answer: A clear and straightforward answer to the original question. Format the result in a human-readable sentence.

Previous conversation history:
{chat_history}

Begin!

New input: {input}
{agent_scratchpad}
"""

# ==============================================================================
# 2. DATASET CONFIGURATIONS (with new 'schema_context')
# ==============================================================================
DATASET_CONFIGS = {
    "Incident_Tracker": {
        # Power BI Connection Details
        "dataset_id": "b0da0357-f866-4c6e-abb9-4976b5ef03a4",
        "table_names": ["Tracker"],
        "llm_persona": "Incident Management Analytics",
        
        # NEW: Column context for the LLM
        "schema_context": """
The only table available is 'Tracker' with the following relevant columns:
| Column Name | Description |
| :--- | :--- |
| **Tracker[Ticket No]** | Unique identifier for incidents (useful for COUNTING). |
| **Tracker[Start date]** | Date incident was initiated. |
| **Tracker[Current status]** | Status of the ticket (e.g., "Open", "Closed"). |
| **Tracker[Incident Category]** | Type of security incident (e.g., "Privilege Misuse", "Process Deviation"). |
| **Tracker[Severity {Low Medium High}]** | The severity level of the incident. |
| **Tracker[Closed date]** | Date incident was closed (used with Start date for ageing). |
| **Tracker[Entity]** | The entity the incident belongs to (e.g., "Straive", "LearningMate"). |
        """,
        
        # Application Custom Content
        "faqs": [
            "What is the total number of open incidents?", 
            "Which is the Most Frequent Incident Category in the entire Dataset?", 
            "Compare the total Number of incidents for LearningMate versus Straive."
        ],
        
        # KEY INSIGHTS QUERY
        "key_insights_query": """
        **TASK: Retrieve two key metrics and generate a concise, single-paragraph summary.**

        **CRITICAL INSTRUCTION:** For both metrics, you MUST use the correct SCALAR DAX structure: EVALUATE CALCULATE(...).

        **Metric 1 (Open Count):** Use 'query_powerbi' with the query to find the total number of open tickets: 
        EVALUATE CALCULATE( COUNTROWS(FILTER(Tracker, Tracker[Current status] = "Open")) )

        **Metric 2 (Avg Ageing):** Use 'query_powerbi' with the query to find the average incident resolution time in days for closed tickets:
        EVALUATE CALCULATE( AVERAGEX( FILTER(Tracker, Tracker[Current status] = "Closed"), DATEDIFF(Tracker[Start date], Tracker[Closed date], DAY) ) )

        **FINAL STEP:** After observing the two numerical results, combine them into a single, concise paragraph summary for the Final Answer. The summary must interpret the volume of open incidents and the average ageing period. The Final Answer MUST NOT contain any DAX, query output, or numbered lists.
        """
    },
    
    # ... (Other dataset entries)
}