# Client Migration Guide

This guide explains how to migrate clients from a CSV file into the Bookngon AI system using the `migrate-clients` management command.

## Overview

The `migrate-clients` command allows you to import client data from a CSV file and associate them with a specific business in the system. This is useful for migrating existing client databases or bulk importing client information.

## CSV File Format

The CSV file should be located in the project root directory (or specify a custom path) and must contain the following columns:

| Column Name | Required | Description | Example |
|------------|----------|-------------|---------|
| `fullname` | Yes | Client's full name | "John Doe" |
| `tel` | No | Phone number | "4377337422" |
| `email` | No | Email address | "john.doe@example.com" |
| `birthday` | No | Date of birth (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) | "1990-07-15" or "1990-07-15 00:00:00" |
| `note` | No | Additional notes about the client | "Prefers morning appointments" |
| `reward_point` | No | Reward points balance | "150" |
| `last_visited` | No | Last visit date | "2024-07-26 00:00:00" |
| `life_time_points` | No | Lifetime points earned | "500" |
| `total_paid` | No | Total amount paid | "462.05" |
| `visit_times` | No | Number of visits | "7" |
| `no_show` | No | No-show flag (0 or 1) | "0" or "1" |

### CSV Example

```csv
fullname,tel,email,birthday,reward_point,last_visited,life_time_points,total_paid,visit_times,note,no_show
Taylor,4377337422,,,0,,0,0.00,0,,0
Rebecca Mukuna,9058182820,,1990-07-15 00:00:00,0,2024-07-26 00:00:00,0,72.15,1,,0
Keisha Gobin,4165180117,keisha.gobin@hotmail.com,1995-07-12 00:00:00,0,2024-10-03 00:00:00,0,462.05,7,,0
```

## Command Usage

### Basic Syntax

```bash
python manage.py migrate-clients --business-id <BUSINESS_ID>
```

### Required Arguments

- `--business-id` (required): The ID of the business to associate all imported clients with. You must have a business created in the system before running this command.

### Optional Arguments

- `--csv-file` (optional): Path to the CSV file. Defaults to `business-clients.csv` in the project root.
- `--dry-run` (optional): Run the migration in test mode without actually creating clients. Useful for validating the CSV file and checking for errors.
- `--skip-duplicates` (optional): Skip clients that already exist in the system (matched by phone number or email address).

## Examples

### Example 1: Basic Migration

Import all clients from `business-clients.csv` and associate them with business ID 1:

```bash
python manage.py migrate-clients --business-id 1
```

### Example 2: Dry Run (Test Mode)

Test the migration without creating any clients:

```bash
python manage.py migrate-clients --business-id 1 --dry-run
```

This will show you:
- How many clients would be created
- Any errors that would occur
- A summary of the migration

### Example 3: Skip Duplicates

Import clients but skip any that already exist (by phone or email):

```bash
python manage.py migrate-clients --business-id 1 --skip-duplicates
```

### Example 4: Custom CSV File Path

Import from a custom CSV file location:

```bash
python manage.py migrate-clients --business-id 1 --csv-file /path/to/my-clients.csv
```

### Example 5: Combined Options

Use multiple options together:

```bash
python manage.py migrate-clients --business-id 1 --csv-file data/clients.csv --dry-run --skip-duplicates
```

## How It Works

1. **Validation**: The command first validates that:
   - The specified business exists
   - The CSV file exists and is readable

2. **Processing**: For each row in the CSV:
   - Parses the client data
   - Maps CSV columns to Client model fields
   - Associates the client with the specified business
   - Creates the client record in the database

3. **Duplicate Handling**:
   - Without `--skip-duplicates`: Uses `update_or_create` to update existing clients or create new ones
   - With `--skip-duplicates`: Skips clients that already exist (matched by phone or email)

4. **Progress Updates**: Shows progress every 100 rows processed

5. **Summary**: Displays a final summary with:
   - Number of clients created
   - Number of clients updated (if duplicates found)
   - Number of rows skipped
   - Number of errors encountered

## Output Example

```
Starting migration from business-clients.csv...
Target business: My Business (ID: 1)
Processed 100 rows...
Processed 200 rows...
...

==================================================
Migration Summary:
==================================================
Created: 150 clients
Updated: 25 clients
Skipped: 10 rows
Errors: 2 rows
==================================================
```

## Data Mapping

The command maps CSV data to the Client model as follows:

- `fullname` → `first_name` (entire name stored in first_name field)
- `tel` → `phone`
- `email` → `email`
- `birthday` → `date_of_birth` (parsed from various date formats)
- `note` + additional info → `notes` (combines note with reward points, total paid, visit times, etc.)
- All clients are set with:
  - `is_active = True`
  - `is_vip = False`
  - `primary_business = <specified business>`

## Troubleshooting

### Error: Business with ID X not found
- **Solution**: Make sure the business exists in the system. You can check business IDs using the Django admin or by querying the database.

### Error: CSV file not found
- **Solution**: Check that the CSV file exists at the specified path. Use `--csv-file` to specify a custom path.

### Error: Could not parse birthday
- **Solution**: The birthday field accepts formats like "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS". Ensure dates are in a valid format.

### Clients not being created
- **Solution**: 
  - Run with `--dry-run` first to see what would happen
  - Check for errors in the output
  - Verify the CSV file has the correct column names
  - Ensure the `fullname` column is not empty for rows you want to import

### Duplicate clients being created
- **Solution**: Use the `--skip-duplicates` flag to skip existing clients, or the command will update existing clients by default if they match by phone or email.

## Best Practices

1. **Always test first**: Use `--dry-run` before running the actual migration
2. **Backup your data**: Make sure you have a backup of your database before running migrations
3. **Check business ID**: Verify the business ID exists before running the command
4. **Validate CSV**: Ensure your CSV file is properly formatted and has the required columns
5. **Handle duplicates**: Decide whether to skip or update duplicate clients before running
6. **Monitor progress**: Watch the output for errors and warnings during migration

## Related Commands

- `python manage.py create_sample_clients`: Create sample client data for testing
- `python manage.py client_stats`: View client statistics
- `python manage.py cleanup_clients`: Clean up duplicate or inactive clients

## Notes

- The command processes CSV files with UTF-8 encoding
- Empty rows or rows without a `fullname` are automatically skipped
- Phone numbers are stored as-is (no automatic formatting)
- The command continues processing even if individual rows fail, showing errors in the summary

