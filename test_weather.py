from tools.weather_tool import get_weather


def main():
    location = "Los Angeles"

    try:
        weather = get_weather(location)

        print("\nWeather Result")
        print("-" * 30)

        for key, value in weather.items():
            print(f"{key}: {value}")

    except Exception as error:
        print(f"Weather request failed: {error}")


if __name__ == "__main__":
    main()