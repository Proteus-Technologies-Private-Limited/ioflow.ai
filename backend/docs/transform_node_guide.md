# Transform Node Guide

## Overview

The Transform Node allows you to write Python-like scripts to transform data as it flows through your workflow. It provides a secure, sandboxed environment for data manipulation with access to local variables, global flow variables, and outputs from other nodes.

## Key Features

- **Secure Execution**: Uses RestrictedPython to prevent malicious code execution
- **Variable Scoping**: Local variables, global variables, and node outputs
- **Built-in Functions**: String and math operations
- **Loop Support**: Process lists and collections
- **Resource Limits**: Execution timeout and iteration limits

## Available Libraries

**Important**: All libraries listed below are pre-imported and available for use. You cannot import additional modules - attempting to use `import` statements will result in an error.

### Document Processing Libraries
The following document processing libraries are available:

- **pandas** (`pd`) - Data manipulation and Excel/CSV operations
- **openpyxl** - Excel file reading and writing
- **docx** - Word document processing
- **pypdf** - PDF text extraction
- **pptx** - PowerPoint presentation handling

### Data Processing Libraries
- **csv** - CSV file operations
- **json** (`json_module`) - JSON parsing and generation
- **base64** (`base64_module`) - Base64 encoding/decoding
- **io** - In-memory file operations (BytesIO, StringIO)
- **collections** - Specialized container datatypes
- **itertools** - Functions for creating iterators
- **re** - Regular expressions
- **datetime** - Date and time operations
- **uuid** - UUID generation
- **hashlib** - Cryptographic hashing
- **math** (`math_module`) - Mathematical functions
- **statistics** - Statistical functions
- **random** - Random number generation
- **decimal** - Decimal fixed point and floating point arithmetic
- **html** - HTML parsing and escaping
- **textwrap** - Text wrapping and formatting
- **unicodedata** - Unicode character database
- **difflib** - Helpers for computing deltas
- **email** - Email parsing and generation

### PDF Generation Libraries
- **reportlab** - PDF generation toolkit

## Available Objects

### 1. `input`
**IMPORTANT**: Contains ONLY trigger variables (manual inputs, webhook payload, event data, etc.). 
This is NOT data from the previous node - it's always the flow's initial trigger data!

```python
# Access trigger variables (NOT previous node data!)
user_email = input.get('user_email', '')  # From manual trigger
webhook_data = input.get('webhook_payload', {})  # From webhook trigger
event_id = input.get('event_id', '')  # From event trigger
```

### 2. `local`
Dictionary for storing local variables within the transform node.

```python
# Store local variables
local['counter'] = 0
local['processed_items'] = []
```

### 3. `global`
Access and set global variables that persist across nodes.

```python
# Read global variable
total = global.get('running_total', 0)

# Set global variable (using set_global function)
set_global('running_total', total + 10)
```

### 4. `node_outputs`
Access outputs from specific nodes that have already executed. You MUST specify the node ID.
This is how you get data from previous nodes (not through `input`!).

```python
# Access specific node output - MUST use node ID!
user_data = node_outputs['fetch_user_api']['data']['user']
processed = node_outputs['transform_1']['processed_items']
api_status = node_outputs['api_call_456']['status']

# To process data from previous node:
previous_result = node_outputs['previous_node_id']['output_field']
```

### 5. `output`
Dictionary where you store the transform output.

```python
# Set the output
output['processed'] = True
output['items'] = local['processed_items']
```

## Built-in Functions

### String Operations (`string`)

- `string['upper'](text)` - Convert to uppercase
- `string['lower'](text)` - Convert to lowercase
- `string['capitalize'](text)` - Capitalize first letter
- `string['title'](text)` - Title case
- `string['strip'](text)` - Remove whitespace
- `string['split'](text, separator)` - Split string
- `string['join'](separator, items)` - Join list of strings
- `string['replace'](text, old, new)` - Replace substring
- `string['startswith'](text, prefix)` - Check prefix
- `string['endswith'](text, suffix)` - Check suffix
- `string['find'](text, substring)` - Find substring index
- `string['count'](text, substring)` - Count occurrences

### Math Operations (`math`)

- `math['add'](a, b)` - Addition
- `math['subtract'](a, b)` - Subtraction
- `math['multiply'](a, b)` - Multiplication
- `math['divide'](a, b)` - Division (returns None if b=0)
- `math['power'](a, b)` - Exponentiation
- `math['sqrt'](x)` - Square root

### Other Functions

- `len(collection)` - Get length
- `min(collection)` - Get minimum value
- `max(collection)` - Get maximum value
- `sum(collection)` - Sum values
- `sorted(collection)` - Sort collection
- `isinstance(obj, type)` - Type checking
- `set_global(name, value)` - Set a global variable
- `print(message)` - Print debug messages to execution logs

## Debugging with Print Statements

Transform nodes support `print()` statements for debugging. All print output appears in the execution logs.

```python
# Print statements for debugging
print("=== Starting Transform Node ===")
print(f"Trigger input keys: {list(input.keys())}")
print(f"Available node outputs: {list(node_outputs.keys())}")

# Debug specific data
user_email = input.get('user_email')
print(f"Processing user: {user_email}")

# Check node output structure
if 'fetch_api' in node_outputs:
    api_data = node_outputs['fetch_api']
    print(f"API response type: {type(api_data)}")
    print(f"API response keys: {api_data.keys() if isinstance(api_data, dict) else 'Not a dict'}")

# Track processing progress
items = node_outputs.get('get_items', {}).get('items', [])
print(f"Processing {len(items)} items...")

for i, item in enumerate(items):
    print(f"  Item {i+1}: {item.get('name', 'unknown')}")
    # Process item...

print("=== Transform Complete ===")

# Set output
output = {'processed': True, 'count': len(items)}
```

## Example Scripts

### 1. Basic Transformation

```python
# Basic data transformation
# Remember: 'input' contains trigger variables, not previous node data!

# From trigger (e.g., manual input)
user_name = input.get('user_name', 'World')
output['greeting'] = f"Hello, {user_name}!"

# From a previous node's output
if 'fetch_data' in node_outputs:
    items = node_outputs['fetch_data'].get('items', [])
    output['item_count'] = len(items)
    output['first_item'] = items[0] if items else None

output['processed'] = True
```

### 2. String Processing

```python
# Process user name
local['first_name'] = input.get('first_name', '')
local['last_name'] = input.get('last_name', '')

# Create full name
local['full_name'] = string['join'](' ', [local['first_name'], local['last_name']])

# Generate email
local['email_base'] = string['lower'](string['replace'](local['full_name'], ' ', '.'))
output['email'] = f"{local['email_base']}@company.com"

# Create initials
output['initials'] = string['upper'](
    local['first_name'][:1] + local['last_name'][:1]
)

output['full_name'] = local['full_name']
output['display_name'] = string['title'](local['full_name'])
```

### 3. List Processing (Inside Transform Node)

```python
# Filter and transform items
local['filtered_items'] = []
local['total_price'] = 0

for item in input.get('items', []):
    if item.get('status') == 'active' and item.get('price', 0) > 0:
        # Transform item
        local['filtered_items'].append({
            'id': item['id'],
            'name': string['upper'](item['name']),
            'price': item['price'],
            'formatted_price': f"${item['price']:.2f}"
        })
        # Calculate total
        local['total_price'] = math['add'](local['total_price'], item['price'])

output['items'] = local['filtered_items']
output['total_price'] = local['total_price']
output['item_count'] = len(local['filtered_items'])
output['average_price'] = math['divide'](local['total_price'], len(local['filtered_items'])) if local['filtered_items'] else 0
```

### 4. Data Aggregation

```python
# Aggregate numeric data
local['values'] = input.get('measurements', [])
local['sum'] = 0
local['count'] = 0
local['min_val'] = None
local['max_val'] = None

for value in local['values']:
    if isinstance(value, (int, float)):
        local['sum'] = math['add'](local['sum'], value)
        local['count'] = math['add'](local['count'], 1)
        
        # Track min/max
        if local['min_val'] is None or value < local['min_val']:
            local['min_val'] = value
        if local['max_val'] is None or value > local['max_val']:
            local['max_val'] = value

# Calculate statistics
output['statistics'] = {
    'sum': local['sum'],
    'count': local['count'],
    'average': math['divide'](local['sum'], local['count']) if local['count'] > 0 else 0,
    'min': local['min_val'],
    'max': local['max_val'],
    'range': math['subtract'](local['max_val'], local['min_val']) if local['min_val'] is not None else 0
}

# Store in global for other nodes to access
set_global('data_stats', output['statistics'])
```

### 5. Conditional Logic

```python
# Process order based on conditions
local['order'] = input.get('order', {})
local['customer'] = local['order'].get('customer', {})

# Determine customer category
if local['customer'].get('total_purchases', 0) > 1000:
    output['customer_tier'] = 'gold'
    output['discount_rate'] = 0.15
elif local['customer'].get('total_purchases', 0) > 500:
    output['customer_tier'] = 'silver'
    output['discount_rate'] = 0.10
else:
    output['customer_tier'] = 'bronze'
    output['discount_rate'] = 0.05

# Calculate order total with discount
local['subtotal'] = local['order'].get('subtotal', 0)
local['discount'] = math['multiply'](local['subtotal'], output['discount_rate'])
output['final_total'] = math['subtract'](local['subtotal'], local['discount'])

# Add order details
output['order_summary'] = {
    'order_id': local['order'].get('id'),
    'customer_name': local['customer'].get('name'),
    'customer_tier': output['customer_tier'],
    'subtotal': local['subtotal'],
    'discount': local['discount'],
    'final_total': output['final_total']
}
```

### 6. Excel to CSV Conversion

```python
# Convert Excel file to CSV
# Note: pandas (as pd), base64, and io modules are pre-imported

# Get base64 encoded Excel file from previous node
excel_base64 = node_outputs['read_excel_file']['content']

# Decode and read Excel
excel_data = base64.b64decode(excel_base64)
xl_file = pd.ExcelFile(io.BytesIO(excel_data))

# Get sheet name from input or use first sheet
sheet_name = input.get('sheet_name', 0)

# Read the Excel sheet
df = pd.read_excel(io.BytesIO(excel_data), sheet_name=sheet_name)

# Convert to CSV
csv_content = df.to_csv(index=False)

# Output results
output['csv_content'] = csv_content
output['csv_base64'] = base64.b64encode(csv_content.encode()).decode()
output['rows'] = len(df)
output['columns'] = len(df.columns)
output['sheet_names'] = xl_file.sheet_names
```

### 7. Word Document to Text/Markdown

```python
# Extract text from Word document
# Note: base64, io, and docx modules are pre-imported

# Get base64 encoded Word file
word_base64 = node_outputs['read_word_file']['content']
word_data = base64.b64decode(word_base64)

# Open Word document
doc = docx.Document(io.BytesIO(word_data))

# Choose output format
output_format = input.get('format', 'text')  # text, markdown, or html

if output_format == 'markdown':
    # Convert to Markdown
    content = []
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading 1'):
            content.append(f"# {para.text}")
        elif para.style.name.startswith('Heading 2'):
            content.append(f"## {para.text}")
        elif para.style.name.startswith('Heading 3'):
            content.append(f"### {para.text}")
        elif para.text.strip():
            content.append(para.text)
    output['content'] = '\n\n'.join(content)
    
elif output_format == 'html':
    # Convert to HTML
    html_parts = ['<html><body>']
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            level = para.style.name[-1]
            html_parts.append(f"<h{level}>{para.text}</h{level}>")
        elif para.text.strip():
            html_parts.append(f"<p>{para.text}</p>")
    html_parts.append('</body></html>')
    output['content'] = '\n'.join(html_parts)
    
else:
    # Plain text
    output['content'] = '\n\n'.join([p.text for p in doc.paragraphs if p.text.strip()])

# Extract tables if present
tables_data = []
for table in doc.tables:
    table_rows = []
    for row in table.rows:
        table_rows.append([cell.text.strip() for cell in row.cells])
    tables_data.append(table_rows)
output['tables'] = tables_data

# Statistics
output['paragraph_count'] = len([p for p in doc.paragraphs if p.text.strip()])
output['word_count'] = len(output['content'].split())
```

### 8. CSV to Excel with Formatting

```python
# Convert CSV to formatted Excel
# Note: pandas (as pd), base64, and io modules are pre-imported

# Get CSV content
csv_base64 = node_outputs['read_csv_file']['content']
csv_data = base64.b64decode(csv_base64).decode('utf-8')

# Read CSV into DataFrame
df = pd.read_csv(io.StringIO(csv_data))

# Data cleaning and type conversion
for col in df.columns:
    # Try to convert to numeric if possible
    try:
        df[col] = pd.to_numeric(df[col])
    except:
        pass
        
# Create Excel with multiple sheets if needed
excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
    # Write main data
    df.to_excel(writer, sheet_name='Data', index=False)
    
    # Add summary sheet if numeric columns exist
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        summary = pd.DataFrame({
            'Column': numeric_cols,
            'Mean': [df[col].mean() for col in numeric_cols],
            'Min': [df[col].min() for col in numeric_cols],
            'Max': [df[col].max() for col in numeric_cols],
            'Count': [df[col].count() for col in numeric_cols]
        })
        summary.to_excel(writer, sheet_name='Summary', index=False)

# Get Excel content
excel_buffer.seek(0)
excel_content = excel_buffer.read()

output['excel_base64'] = base64.b64encode(excel_content).decode()
output['rows'] = len(df)
output['columns'] = list(df.columns)
output['has_summary'] = len(numeric_cols) > 0
```

### 9. PDF Text Extraction

```python
# Extract text from PDF
# Note: pypdf, base64, and io modules are pre-imported

# Get PDF content
pdf_base64 = node_outputs['read_pdf_file']['content']
pdf_data = base64.b64decode(pdf_base64)

# Create PDF reader
reader = pypdf.PdfReader(io.BytesIO(pdf_data))

# Extract text from all pages
full_text = []
page_texts = []

for page_num, page in enumerate(reader.pages):
    page_text = page.extract_text()
    page_texts.append({
        'page': page_num + 1,
        'text': page_text,
        'char_count': len(page_text)
    })
    full_text.append(page_text)

# Combine all text
output['full_text'] = '\n\n--- Page Break ---\n\n'.join(full_text)
output['pages'] = page_texts
output['total_pages'] = len(reader.pages)
output['total_characters'] = sum(p['char_count'] for p in page_texts)

# Extract metadata if available
metadata = reader.metadata
if metadata:
    output['metadata'] = {
        'title': str(metadata.get('/Title', '')),
        'author': str(metadata.get('/Author', '')),
        'subject': str(metadata.get('/Subject', '')),
        'creator': str(metadata.get('/Creator', ''))
    }
```

### 10. Multi-Format Document Processing

```python
# Process documents based on file type
# Note: os, base64, and io modules are pre-imported

# Get file info
file_name = input.get('file_name', '')
file_extension = os.path.splitext(file_name)[1].lower()
file_base64 = input.get('file_content', '')

# Decode file
file_data = base64.b64decode(file_base64)

output['source_file'] = file_name
output['file_type'] = file_extension

# Process based on file type
if file_extension in ['.xlsx', '.xls']:
    # Excel file
    df = pd.read_excel(io.BytesIO(file_data))
    output['data_type'] = 'spreadsheet'
    output['rows'] = len(df)
    output['columns'] = list(df.columns)
    output['preview'] = df.head(10).to_dict('records')
    
elif file_extension in ['.docx', '.doc']:
    # Word document
    doc = docx.Document(io.BytesIO(file_data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    output['data_type'] = 'document'
    output['paragraphs'] = len(paragraphs)
    output['preview'] = '\n\n'.join(paragraphs[:5])
    
elif file_extension == '.pdf':
    # PDF file
    reader = pypdf.PdfReader(io.BytesIO(file_data))
    output['data_type'] = 'pdf'
    output['pages'] = len(reader.pages)
    output['preview'] = reader.pages[0].extract_text()[:500] if reader.pages else ''
    
elif file_extension == '.csv':
    # CSV file
    csv_text = file_data.decode('utf-8')
    df = pd.read_csv(io.StringIO(csv_text))
    output['data_type'] = 'csv'
    output['rows'] = len(df)
    output['columns'] = list(df.columns)
    output['preview'] = df.head(10).to_dict('records')
    
else:
    output['data_type'] = 'unsupported'
    output['error'] = f'File type {file_extension} is not supported'

output['processed'] = True
```

### 11. Working with Node Outputs

```python
# Combine data from multiple nodes
local['user_data'] = node_outputs.get('fetch_user', {}).get('data', {})
local['order_data'] = node_outputs.get('fetch_orders', {}).get('orders', [])
local['api_status'] = node_outputs.get('api_call', {}).get('status', 'unknown')

# Process combined data
output['user_summary'] = {
    'name': local['user_data'].get('name', 'Unknown'),
    'email': local['user_data'].get('email', ''),
    'order_count': len(local['order_data']),
    'total_spent': sum(order.get('total', 0) for order in local['order_data']),
    'api_status': local['api_status']
}

# Update global counter
current_count = global.get('processed_users', 0)
set_global('processed_users', math['add'](current_count, 1))
```

## Working with Loop Nodes

### Loop Variables in Transform Nodes

Loop variables (`loop.item`, `loop.counter`, `loop.index`, etc.) are **ONLY available inside loop nodes**. A transform node must be connected within a loop's body to access these variables.

#### Loop Node Structure
Loop nodes have special connection handles:
- **loop-body**: Output handle that connects to nodes inside the loop
- **loop-back**: Input handle that receives connections from nodes to continue the loop
- **continue**: Output handle that connects to nodes after the loop completes

#### Example: Transform Node Inside a Loop
```python
# This transform node is INSIDE a loop (connected from loop-body)
# Loop variables are available here

# Access the current loop item
current_item = loop.item  # For forEach loops
counter_value = loop.counter  # For for loops
index = loop.index  # Current iteration index

# Process the item
processed_item = {
    'id': current_item.get('id'),
    'name': string['upper'](current_item.get('name', '')),
    'index': index
}

# Set output
output = processed_item
```

#### Example: Transform Node OUTSIDE a Loop
```python
# This transform node is OUTSIDE a loop
# Loop variables are NOT available here - will cause validation errors

# WRONG - This will fail validation:
# item = loop.item  # ERROR: loop variables not available

# CORRECT - Access data from other nodes:
data = node_outputs.get('previous_node', {})
output = {'processed': data}
```

#### Correct Loop Flow Structure
```
Trigger → Loop Node → [loop-body] → Transform/Action Nodes → [loop-back] → Loop Node
                    ↓
              [continue] → Nodes after loop
```

#### Breaking Out of Loops
To exit a loop early, use a condition node inside the loop:
```
Loop → [loop-body] → Condition → [true] → Action → Exit to outside loop
                              ↓
                          [false] → Continue processing → [loop-back] → Loop
```

## Best Practices

1. **Always use `.get()` for dictionary access** to avoid KeyError
2. **Initialize local variables** before using them in loops
3. **Check data types** before performing operations
4. **Use meaningful variable names** for readability
5. **Add comments** to explain complex logic
6. **Set result incrementally** rather than all at once
7. **Handle edge cases** like empty lists or None values

## Document Processing Capabilities

The transform node now supports comprehensive document processing:

### Supported Conversions
- **Excel to CSV** - Convert .xlsx/.xls files to CSV format
- **CSV to Excel** - Convert CSV files to formatted Excel with multiple sheets
- **Word to Text** - Extract plain text from .docx/.doc files
- **Word to Markdown** - Convert Word documents to Markdown format
- **Word to HTML** - Convert Word documents to HTML
- **PDF to Text** - Extract text content from PDF files
- **Text to Word** - Create Word documents from plain text

### Working with Files
All file operations use base64 encoding for safe binary data handling:

1. **Reading Files**: Files are read as base64 from File Systems services
2. **Processing**: Decode base64 → Process with pandas/docx/pypdf → Encode result
3. **Writing Files**: Output as base64 for File Systems write services

### Data Analysis with Pandas
- Read and write Excel files with multiple sheets
- Data cleaning and type conversion
- Statistical analysis and aggregation
- DataFrame operations and transformations
- CSV parsing with automatic type detection

## Limitations

1. **No imports** - Cannot import Python modules (all libraries are pre-imported)
2. **No file operations** - Cannot read/write files directly (use File Systems services)
3. **No network calls** - Cannot make HTTP requests
4. **Execution timeout** - Scripts timeout after 5 seconds
5. **Iteration limit** - Maximum 10,000 iterations
6. **Output size limit** - Maximum 50MB output size (configurable)

## Error Handling

If your script encounters an error, the transform node will fail and the error message will be logged. Common errors include:

- **KeyError**: Accessing dictionary key that doesn't exist (use `.get()`)
- **TypeError**: Operating on wrong data type (check with `isinstance()`)
- **ZeroDivisionError**: Division by zero (check denominator first)
- **Timeout**: Script takes too long (optimize loops)
- **Iteration limit**: Too many loop iterations (reduce data size or optimize)

## Security

The transform node uses RestrictedPython to ensure safe execution:

- No access to system resources
- No ability to import modules
- No access to dangerous built-ins
- Limited execution time and resources
- All operations are sandboxed

This makes it safe to run user-provided scripts without risk to the system.

## JSON Formatting for Transform Scripts

### Important: How to Write Transform Node Scripts in JSON

When creating transform nodes, the script should be written as a regular Python script with actual newlines. The JSON serialization process will handle the escaping automatically.

### Correct Approach

#### Step 1: Write your Python script normally
```python
import base64
import pandas as pd

file_info = input.get('file_upload')
file_name = file_info.get('name')

output = {
    'file_name': file_name,
    'processed': True
}
```

#### Step 2: When creating the JSON structure
```python
# In Python, when building the flow:
# Method 1: Use string concatenation with parentheses for multi-line strings
script = (
    "import base64\n"
    "import pandas as pd\n"
    "\n"
    "file_info = input.get('file_upload')\n"
    "file_name = file_info.get('name')\n"
    "\n"
    "output = {\n"
    "    'file_name': file_name,\n"
    "    'processed': True\n"
    "}"
)

# Method 2: Build script as a single line with explicit \n
script = "import base64\nimport pandas as pd\n\nfile_info = input.get('file_upload')\nfile_name = file_info.get('name')\n\noutput = {\n    'file_name': file_name,\n    'processed': True\n}"

node = {
    "type": "transform",
    "data": {
        "script": script  # Use the string with escaped newlines
    }
}

# Let json.dumps handle any additional escaping
import json
flow_json = json.dumps(node)  # This properly escapes the content
```

#### Step 3: The resulting JSON will have escaped newlines
When serialized, the JSON will look like:
```json
{
  "type": "transform",
  "data": {
    "script": "import base64\nimport pandas as pd\n\nfile_info = input.get('file_upload')\nfile_name = file_info.get('name')\n\noutput = {\n    'file_name': file_name,\n    'processed': True\n}"
  }
}
```

### Key Points

1. **Write Python naturally**: Use actual newlines when writing the script
2. **Don't manually escape**: Don't try to add `\n` yourself
3. **Use proper JSON serialization**: Use `json.dumps()` or equivalent
4. **The system handles it**: The backend will correctly parse and execute the script

### Common Mistakes to Avoid

#### ❌ DON'T use triple quotes in transform scripts
```python
# WRONG - Don't use triple quotes:
# script = '''This is wrong
# It will cause JSON validation errors'''
```
Triple quotes cause JSON parsing issues.

#### ❌ DON'T manually add double escape sequences
```python
# WRONG - Don't do this:
script = "import base64\\nimport pandas as pd\\n\\nfile_info = input.get('file_upload')"
```
This creates double escaping and won't work correctly.

#### ❌ DON'T try to construct JSON strings manually
```python
# WRONG - Don't do this:
flow_json = '{"script": "line1\\nline2\\nline3"}'
```

#### ✅ DO use string concatenation or single strings with \n
```python
# CORRECT - Method 1: String concatenation
script = (
    "line1\n"
    "line2\n"
    "line3"
)

# CORRECT - Method 2: Single string with escaped newlines
script = "line1\nline2\nline3"

flow_json = json.dumps({"script": script})
```

### For Agents and LLMs

When generating transform node scripts:
1. Write the Python code with normal formatting for planning
2. When creating the actual script field:
   - Use string concatenation with parentheses for readability
   - OR use a single string with \n escape sequences
   - NEVER use triple quotes (''' or """)
3. Use standard JSON serialization to create the final output
4. The validation system will accept properly formatted JSON

#### Handling Multi-line Prompts in Scripts
When you need multi-line text in your transform scripts (e.g., for prompts):
```python
# CORRECT: Use parentheses for concatenation
prompt_template = (
    'Extract data from the document.\n'
    'Format as JSON with the following structure:\n'
    '{ "field1": "value1", "field2": "value2" }'
)

# ALSO CORRECT: Use escape sequences in a single string
prompt_template = 'Extract data from the document.\nFormat as JSON with the following structure:\n{ "field1": "value1", "field2": "value2" }'

# WRONG: Don't use triple quotes - they cause JSON validation errors
# prompt_template = '''Extract data...'''  # This will fail
```

### Example: Complete Transform Node

```json
{
  "id": "transform_1",
  "type": "transform",
  "position": {"x": 300, "y": 200},
  "data": {
    "label": "Process Data",
    "script": "# This is a complete example\nimport json\n\n# Get input data\ndata = input.get('data', {})\n\n# Process the data\nprocessed = {\n    'original': data,\n    'count': len(data),\n    'timestamp': datetime.now().isoformat()\n}\n\n# Set output\noutput = processed"
  }
}
```

Note how the script appears as a single line with `\n` escape sequences in the JSON, but this is handled automatically by JSON serialization.