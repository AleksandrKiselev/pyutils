import random
import string

def generate_password(length=12):
    """
    Password generator.
    :param length: Length of the password (default is 12 characters)
    :return: Randomly generated password
    """
    if length < 4:
        raise ValueError("Password length must be at least 4 characters.")

    # Define character sets
    letters = string.ascii_letters  # Letters (a-z, A-Z)
    digits = string.digits          # Digits (0-9)
    symbols = string.punctuation    # Special characters (!, @, #, etc.)

    # Ensure at least one character from each set is included
    password = [
        random.choice(letters),     # At least one letter
        random.choice(digits),      # At least one digit
        random.choice(symbols)      # At least one special character
    ]

    # Add remaining characters to meet the desired length
    all_characters = letters + digits + symbols
    password += random.choices(all_characters, k=length - len(password))

    # Shuffle the characters to randomize the password
    random.shuffle(password)

    return ''.join(password)

# Example usage
if __name__ == "__main__":
    try:
        length = int(input("Enter the desired password length: "))
        password = generate_password(length)
        print(f"Generated password: {password}")
    except ValueError as e:
        print(f"Error: {e}")
