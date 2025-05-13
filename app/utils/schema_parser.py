import os
from app.utils.logger import logger

def parse_schema_summary(schema_dir: str = None):
    from app.config import SCHEMA_DIR
    schema_dir = schema_dir or SCHEMA_DIR
    schema_file = os.path.join(schema_dir, "schema_summary.txt")
    with open(schema_file, 'r') as f:
        content = f.read()
    schema_data = {}
    collection_sections = content.split("\nCollection: ")
    for section in collection_sections[1:]:
        lines = section.strip().split("\n")
        collection_name = lines[0].strip()
        collection_info = {"description": "", "fields": []}
        current_field = None
        for line in lines[1:]:
            if line.startswith("Description:"):
                collection_info["description"] = line.replace("Description:", "").strip()
            elif line.strip().startswith("- "):
                if current_field:
                    collection_info["fields"].append(current_field)
                field_line = line.strip("- ").strip()
                try:
                    name, type_info = field_line.split(" (", 1)
                    field_type, mode = type_info.rstrip(")").split(", ")
                except Exception:
                    name = field_line
                    field_type = "unknown"
                    mode = "Nullable"
                current_field = {
                    "name": name.strip(),
                    "type": field_type.strip(),
                    "mode": mode.strip(),
                    "description": ""
                }
            elif line.strip().startswith("Description:") and current_field:
                current_field["description"] = line.replace("Description:", "").strip()
        if current_field:
            collection_info["fields"].append(current_field)
        schema_data[collection_name] = collection_info
    return schema_data
