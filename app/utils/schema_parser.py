import os
from app.utils.logger import logger
from app.config import settings # 

def parse_schema_summary(schema_dir_param: str = None): # Renamed param to avoid conflict
    # Use the schema_dir from settings if no parameter is passed
    actual_schema_dir = schema_dir_param or settings.schema_dir # <<< ACCESS via settings.schema_dir
    schema_file = os.path.join(actual_schema_dir, "schema_summary.txt")
    try:
        with open(schema_file, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        logger.error(f"Schema summary file not found at: {schema_file}")
        # Handle this case appropriately, e.g., return empty dict or raise an error
        return {}
    except Exception as e:
        logger.error(f"Error reading schema summary file {schema_file}: {e}")
        return {}

    schema_data = {}
    # Make sure content is not empty before splitting
    if not content.strip():
        logger.warning(f"Schema summary file is empty: {schema_file}")
        return {}

    collection_sections = content.split("\nCollection: ")
    for section in collection_sections[1:]: # Skip the first item if it's empty before "Collection:"
        lines = section.strip().split("\n")
        if not lines:
            continue
        collection_name = lines[0].strip()
        collection_info = {"description": "", "fields": []}
        current_field = None
        for line in lines[1:]:
            if line.startswith("Description:"):
                # Check if this description belongs to the collection or a field
                if current_field is None:
                    collection_info["description"] = line.replace("Description:", "").strip()
                elif current_field: # Description for the current field
                    current_field["description"] = line.replace("Description:", "").strip()
            elif line.strip().startswith("- "):
                if current_field: # Save the previous field before starting a new one
                    collection_info["fields"].append(current_field)
                field_line = line.strip("- ").strip()
                try:
                    name, type_info = field_line.split(" (", 1)
                    field_type, mode = type_info.rstrip(")").split(", ")
                except ValueError: # Handles cases where split might fail
                    logger.warning(f"Could not parse field line: '{field_line}' in collection '{collection_name}'")
                    name = field_line
                    field_type = "unknown"
                    mode = "Nullable" # Default mode
                current_field = {
                    "name": name.strip(),
                    "type": field_type.strip(),
                    "mode": mode.strip(),
                    "description": "" # Initialize description for the field
                }
            # This condition was a bit problematic. Descriptions for fields might not always start with "Description:"
            # The logic above for line.startswith("Description:") and current_field should handle it better.
            # elif line.strip().startswith("Description:") and current_field:
            #     current_field["description"] = line.replace("Description:", "").strip()

        if current_field: # Append the last field processed
            collection_info["fields"].append(current_field)
        schema_data[collection_name] = collection_info
    return schema_data