from tools.sql_tool import execute_sql

result = execute_sql("""
    SELECT
        risk_classification,
        COUNT(*) AS total
    FROM logistics
    GROUP BY risk_classification
    ORDER BY total DESC;
""")

print(result)