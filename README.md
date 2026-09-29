# Factorial Program in C

## Project Title
**Factorial of a Number Using C**

## Objective
To write a C program that reads a number from the user and calculates its factorial using a `for` loop.

## Formula
For a non-negative integer `n`:

`n! = 1 × 2 × 3 × ... × n`

Special case:

`0! = 1`

## Features
- Accepts an integer from the user.
- Calculates factorial using a `for` loop.
- Handles negative numbers.
- Displays the calculated factorial.

## Files

```text
Factorial_Project/
├── Screenshots/
│   ├── factorial_output_5.png
│   └── factorial_output_10.png
├── Data.txt
├── README.md
└── factorial_code.txt
```

## How to Run

### Using GCC / Git Bash

1. Save the program from `factorial_code.txt` as `factorial.c`.
2. Open Git Bash in that folder.
3. Compile:

```bash
gcc factorial.c -o factorial
```

4. Run:

```bash
./factorial
```

### Example

```text
Enter a number: 5
Factorial of 5 = 120
```

## Test Cases

| Input | Expected Output |
|---:|---:|
| 5 | 120 |
| 0 | 1 |
| 7 | 5040 |
| 10 | 3628800 |
| -3 | Negative number message |

## Conclusion
The project demonstrates the use of variables, input/output, conditional statements, and loops in C to calculate the factorial of a number.
