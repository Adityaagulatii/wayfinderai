import io
import json
import pandas as pd
import networkx as nx
import anthropic
from utils.navigation_engine import build_graph_from_df

class AdminSuite:
    def __init__(self, api_key, model="claude-3-5-sonnet-20240620"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def parse_visual_layout(self, image_b64):
        """
        Admin Agent 1: Layout Parser (Visual)
        Uses Claude Vision to extract a navigation graph from a floorplan image.
        """
        prompt = """
        Act as an Architectural Data Parser. Analyze this floorplan image and extract 
        the logical navigation network. Identify aisles, rooms, and their connections.
        Return ONLY a JSON object with this structure:
        {
            "nodes": [
                {"id": "A1", "name": "Pharmacy", "connects_to": ["A2", "E1"]},
                {"id": "E1", "name": "Entrance", "connects_to": ["A1"]}
            ]
        }
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        return json.loads(response.content[0].text)

    def process_csv_upload(self, csv_file_contents):
        """
        Admin Agent 2: Product Populator (Structured)
        Converts the uploaded CSV into a NetworkX graph for the Navigation Engine.
        """
        df = pd.read_csv(io.StringIO(csv_file_contents))
        # Logic delegated to utility engine to keep agents clean
        graph = build_graph_from_df(df)
        return graph, df

    def run_accessibility_audit(self, graph_data):
        """
        Admin Agent 3: Accessibility Auditor
        Scans the building layout to identify potential "blind spots" or 
        areas requiring more audio landmarks.
        """
        prompt = f"""
        Review this indoor navigation graph for a visually impaired user: {graph_data}.
        Identify 3 potential navigation risks (e.g., long paths without turns, 
        lack of identifiable landmarks) and suggest improvements.
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_sensory_descriptions(self, aisle_name, products):
        """
        Admin Agent 4: Audio Description Generator
        Converts raw aisle data into rich, sensory-focused natural language.
        """
        prompt = f"""
        Create a 2-sentence audio description for a blind user entering the {aisle_name}.
        The area contains: {products}. 
        Mention non-visual cues like typical sounds, smells, or floor textures.
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
