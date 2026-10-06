from tools.sql_tool import execute_sql


def main():
    query = """
    DROP TABLE logistics;
    """

    try:
        result = execute_sql(query)

        print("\nQuery successful:\n")

        for row in result:
            print(row)

    except Exception as error:
        print(f"\nQuery failed: {error}")


if __name__ == "__main__":
    main()