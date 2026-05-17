#!/usr/bin/env python3
"""
Auto-generate API documentation from OpenAPI spec
"""

import json
import sys
from pathlib import Path

def generate_markdown(openapi_spec: dict) -> str:
    """Generate Markdown documentation from OpenAPI spec"""
    
    md = []
    
    md.append("# TradeLab API Documentation\n")
    md.append(f"**Version:** {openapi_spec.get('info', {}).get('version', '1.0.0')}\n")
    md.append(f"**Description:** {openapi_spec.get('info', {}).get('description', '')}\n")
    
    md.append("## Base URL\n")
    md.append("```\nhttp://localhost:8000/api/v1\n```\n")
    
    md.append("## Authentication\n")
    md.append("Currently no authentication required (development mode).\n")
    
    md.append("## Endpoints\n")
    
    for path, methods in sorted(openapi_spec.get('paths', {}).items()):
        for method, details in methods.items():
            if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                continue
            
            md.append(f"### {method.upper()} {path}\n")
            
            if details.get('summary'):
                md.append(f"**{details['summary']}**\n")
            
            if details.get('description'):
                md.append(f"{details['description']}\n")
            
            if details.get('parameters'):
                md.append("**Query Parameters:**\n")
                md.append("| Name | Type | Required | Description |\n")
                md.append("|------|------|----------|-------------|\n")
                for p in details['parameters']:
                    required = 'Yes' if p.get('required') else 'No'
                    desc = p.get('description', '')[:50]
                    md.append(f"| `{p['name']}` | {p.get('type', 'string')} | {required} | {desc} |\n")
                md.append("\n")
            
            if details.get('requestBody'):
                md.append("**Request Body:**\n")
                rb = details['requestBody']
                if rb.get('content'):
                    for ct, content in rb['content'].items():
                        if ct == 'application/json' and content.get('schema'):
                            schema = content['schema']
                            md.append("```json\n")
                            md.append(f"{json.dumps(generate_example(schema), indent=2)}\n")
                            md.append("```\n")
            
            md.append("---\n\n")
    
    md.append("## WebSocket\n\n")
    md.append("### Connection\n")
    md.append("```\nWS /ws\n```\n\n")
    md.append("### Subscribe to Channels\n")
    md.append("```json\n")
    md.append('{"type": "subscribe", "channels": ["channel:dashboard", "channel:decision"]}\n')
    md.append("```\n\n")
    md.append("### Available Channels\n")
    md.append("- `channel:dashboard` - Dashboard updates\n")
    md.append("- `channel:decision` - Decision updates\n")
    md.append("- `channel:risk` - Risk updates\n")
    md.append("- `channel:position` - Position updates\n")
    md.append("- `channel:timeline` - Event timeline updates\n")
    md.append("- `channel:signal` - Signal updates\n")
    md.append("- `channel:order` - Order updates\n")
    
    return ''.join(md)


def generate_example(schema: dict, depth: int = 0) -> dict:
    """Generate example from JSON schema"""
    if depth > 5:
        return {}
    
    if schema.get('type') == 'object':
        result = {}
        for prop, prop_schema in schema.get('properties', {}).items():
            result[prop] = generate_example(prop_schema, depth + 1)
        return result
    
    if schema.get('type') == 'array':
        return [generate_example(schema.get('items', {}), depth + 1)]
    
    if schema.get('type') == 'string':
        if schema.get('format') == 'date-time':
            return "2024-01-01T00:00:00"
        return "string"
    
    if schema.get('type') == 'number' or schema.get('type') == 'integer':
        return 0
    
    if schema.get('type') == 'boolean':
        return True
    
    return None


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate API documentation')
    parser.add_argument('--spec', default='http://localhost:8000/openapi.json', 
                       help='OpenAPI spec URL or file path')
    parser.add_argument('--output', '-o', default='docs/API.md',
                       help='Output file path')
    args = parser.parse_args()
    
    if args.spec.startswith('http'):
        import urllib.request
        with urllib.request.urlopen(args.spec) as response:
            spec = json.loads(response.read())
    else:
        with open(args.spec) as f:
            spec = json.load(f)
    
    md = generate_markdown(spec)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(md)
    
    print(f"Documentation generated: {output_path}")


if __name__ == '__main__':
    main()
