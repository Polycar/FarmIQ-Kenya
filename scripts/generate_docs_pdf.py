from fpdf import FPDF
import os

class DocPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(22, 163, 74)
        self.cell(0, 10, 'FarmIQ Scientific Overhaul Documentation', ln=True, align='C')
        self.set_font('helvetica', 'I', 10)
        self.set_text_color(100)
        self.cell(0, 10, 'Technical Rationale and Agricultural Impact', ln=True, align='C')
        self.ln(10)
        self.set_draw_color(230)
        self.line(10, 32, 200, 32)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def create_report():
    pdf = DocPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font('helvetica', '', 11)
    pdf.set_text_color(0)

    def add_section(title, text):
        pdf.set_font('helvetica', 'B', 13)
        pdf.ln(5)
        pdf.cell(0, 7, title, ln=True)
        pdf.set_font('helvetica', '', 11)
        pdf.multi_cell(0, 6, text)
        pdf.ln(2)

    add_section("1. Executive Summary", 
                "Over the course of system upgrades, the recommendations engine shifted entirely from rigid hardcoded parameters to dynamic satellite-driven models. By linking raw NPK crop removal metrics with precise data, guidelines evaluate realistic agronomic requirements efficiently.")

    add_section("2. Aluminium Toxicity & Acidity Buffering", 
                "Prior calculations incorrectly applied toxic constraints universally. Scientific boundaries dictate Aluminium only dissolves aggressively beneath pH 5.5 filters. Interventions now account for texture buffering limits automatically.")

    add_section("3. Integrating Potassium (K) and Sulfur (S)", 
                "Potassium and Sulfur integrations resolve critical gaps. Because Nitrogen cannot optimize yields without Sulfur support structures, conditional guidelines prevent standard Urea applications dynamically.")

    add_section("4. Target Yields & Cation Exchange Capacity (CEC)", 
                "CEC logic ensures lightweight porous substrates split allocations safely against toxic runoff risks.")

    pdf.output("scientific_impact_report.pdf")
    print("PDF successfully generated.")

if __name__ == '__main__':
    create_report()
