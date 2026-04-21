import os
from fpdf import FPDF

class DevelopmentReport(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.set_text_color(22, 163, 74)
        self.cell(190, 10, 'FarmIQ Kenya: Official Development Record', new_x="LMARGIN", new_y="NEXT", align='L')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def generate_pdf(md_path, pdf_output_path):
    pdf = DevelopmentReport()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found.")
        return

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.readlines()

    for line in content:
        line = line.strip()
        
        # Heading 1
        if line.startswith('# '):
            pdf.ln(5)
            pdf.set_font('helvetica', 'B', 18)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(180, 10, line[2:])
            pdf.ln(2)
        
        # Heading 2
        elif line.startswith('## '):
            pdf.ln(4)
            pdf.set_font('helvetica', 'B', 14)
            pdf.set_text_color(22, 163, 74)
            pdf.multi_cell(180, 10, line[3:])
            pdf.ln(2)
            
        # Heading 3
        elif line.startswith('### '):
            pdf.ln(2)
            pdf.set_font('helvetica', 'B', 12)
            pdf.set_text_color(51, 51, 51)
            pdf.multi_cell(180, 8, line[4:])
            
        # Bullet points
        elif line.startswith('- '):
            pdf.set_font('helvetica', '', 11)
            pdf.set_text_color(0, 0, 0)
            pdf.set_x(20) # Manual indent
            pdf.multi_cell(170, 7, f'* {line[2:]}')
            
        # Divider
        elif line.startswith('---'):
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
            pdf.ln(5)
            
        # Regular text
        else:
            pdf.set_font('helvetica', '', 11)
            pdf.set_text_color(0, 0, 0)
            clean_line = line.replace('**', '').replace('🌱', '').replace('🧬', '').strip()
            if clean_line:
                pdf.multi_cell(180, 7, clean_line)

    pdf.output(pdf_output_path)
    print(f"✅ Success: PDF generated at {pdf_output_path}")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MD_FILE = os.path.join(BASE_DIR, "..", "docs", "development_history.md")
    PDF_FILE = os.path.join(BASE_DIR, "..", "FarmIQ_Development_Documentation.pdf")
    
    generate_pdf(MD_FILE, PDF_FILE)
