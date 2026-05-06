#!/usr/bin/env python3
"""Simple HTTP server for Paper Agent Markdown Viewer."""

import os
import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote


class PaperAgentHandler(SimpleHTTPRequestHandler):
    """Custom handler for Paper Agent viewer."""

    def __init__(self, *args, **kwargs):
        # Set the directory to serve files from
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/api/files':
            self.send_files_list()
        elif self.path.startswith('/outputs/'):
            # Serve files from outputs directory
            self.serve_outputs_file()
        else:
            # Serve static files from viewer directory
            super().do_GET()

    def serve_outputs_file(self):
        """Serve files from outputs directory."""
        try:
            # Remove /outputs/ prefix and decode URL
            file_path = unquote(self.path[9:])  # Remove '/outputs/'
            full_path = Path(__file__).parent.parent / 'outputs' / file_path

            # Security check: ensure path is within outputs directory
            outputs_dir = Path(__file__).parent.parent / 'outputs'
            if not full_path.resolve().is_relative_to(outputs_dir.resolve()):
                self.send_error(403, 'Access denied')
                return

            if not full_path.exists():
                self.send_error(404, 'File not found')
                return

            # Determine content type
            content_type = 'application/octet-stream'
            if full_path.suffix == '.md':
                content_type = 'text/markdown; charset=utf-8'
            elif full_path.suffix in ['.png', '.jpg', '.jpeg']:
                content_type = f'image/{full_path.suffix[1:]}'
            elif full_path.suffix == '.pdf':
                content_type = 'application/pdf'

            # Send file
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', full_path.stat().st_size)
            self.end_headers()

            with open(full_path, 'rb') as f:
                self.wfile.write(f.read())

        except Exception as e:
            self.send_error(500, f'Error: {str(e)}')

    def send_files_list(self):
        """Send list of markdown files."""
        try:
            outputs_dir = Path(__file__).parent.parent / 'outputs'
            files = []

            # Scan for markdown files
            for folder in ['cards', 'deep_notes', 'reports']:
                folder_path = outputs_dir / folder
                if folder_path.exists():
                    for md_file in folder_path.glob('**/*.md'):
                        rel_path = md_file.relative_to(outputs_dir)
                        files.append({
                            'name': md_file.name,
                            'path': f'/outputs/{rel_path}',
                            'folder': folder,
                            'size': md_file.stat().st_size,
                            'modified': md_file.stat().st_mtime
                        })

            # Sort by modified time (newest first)
            files.sort(key=lambda x: x['modified'], reverse=True)

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode())

        except Exception as e:
            self.send_error(500, f'Error: {str(e)}')

    def end_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()


def main():
    """Start the server."""
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, PaperAgentHandler)

    print('=' * 60)
    print('📚 Paper Agent Markdown Viewer')
    print('=' * 60)
    print(f'Server running at: http://localhost:{port}')
    print(f'Open in browser:   http://localhost:{port}/index.html')
    print('=' * 60)
    print('Press Ctrl+C to stop the server')
    print()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n\nServer stopped.')


if __name__ == '__main__':
    main()
