import json

with open("preview.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("SUMMARY:", d.get("summary"))

unknown = d.get("summary", {}).get("unknown_subjects", [])
print("\nUNKNOWN subjects (first 30):")
print(unknown[:30])

preview = d.get("preview", [])
print("\nPreview rows:", len(preview))
if preview:
    print("First row pin:", preview[0].get("pin"))
    print("First row name:", preview[0].get("name"))
    print("First row attendance:", preview[0].get("attendance"))

    print("\nFirst row subjects (first 5):")
    for s in preview[0].get("subjects", [])[:5]:
        print("  sub_code:", s.get("sub_code"),
              "in_master:", s.get("in_master"),
              "valid:", s.get("valid"),
              "error:", s.get("error"),
              "raw:", s.get("raw"))
