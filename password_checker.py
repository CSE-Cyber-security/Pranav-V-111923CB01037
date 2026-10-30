import string

def check_password(password):
    """Return the result of each password-strength criterion."""
    return {
        "Length (at least 8 characters)": len(password) >= 8,
        "Uppercase letter (A-Z)": any(char.isupper() for char in password),
        "Lowercase letter (a-z)": any(char.islower() for char in password),
        "Number (0-9)": any(char.isdigit() for char in password),
        "Symbol (!@#$%^&*)": any(char in string.punctuation for char in password),
    }


def get_strength(results):
    score = sum(results.values())

    if score == 5:
        return "STRONG"
    elif score >= 3:
        return "MODERATE"
    return "WEAK"


def main():
    print("=== Password Strength Checker ===")

    while True:
        password = input("\nEnter your password (or type 'exit' to quit): ")

        if password.lower() == "exit":
            print("Thank you! Goodbye!")
            break

        results = check_password(password)

        print("\nPassword Analysis:")
        for criterion, satisfied in results.items():
            status = "Satisfied" if satisfied else "Not satisfied"
            symbol = "✓" if satisfied else "✗"
            print(f"{symbol} {criterion}: {status}")

        print(f"\nPassword Strength: {get_strength(results)}")

        another = input("\nDo you want to check another password? (y/n): ")
        if another.lower() != "y":
            print("Thank you! Goodbye!")
            break


if __name__ == "__main__":
    main()
