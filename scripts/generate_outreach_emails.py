from fpdf import FPDF
import os

class OutreachPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 14)
        self.set_text_color(22, 163, 74)
        self.cell(0, 10, 'FarmIQ Outreach Templates', ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def build_pdf():
    pdf = OutreachPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font('helvetica', '', 11)

    def add_email(org_type, subject, body):
        pdf.set_font('helvetica', 'B', 12)
        pdf.set_text_color(37, 99, 235)
        pdf.cell(0, 7, org_type, ln=True)
        pdf.set_font('helvetica', 'I', 10)
        pdf.set_text_color(100)
        pdf.cell(0, 6, f"Subject: {subject}", ln=True)
        pdf.ln(2)
        pdf.set_font('helvetica', '', 11)
        pdf.set_text_color(0)
        pdf.multi_cell(0, 6, body)
        pdf.ln(10)

    add_email(
        "1. Research Partners (KALRO / AGRA)",
        "Collaboration Proposal: Next-Gen Precision Soil Analytics (FarmIQ Kenya)",
        "Dear Team,\n\nWe have built FarmIQ, a mobile-first precision agriculture platform mapping high-fidelity soil nutrient profiles across all 47 Kenyan counties.\n\nWe would welcome the opportunity to discuss a brief collaboration to validate baseline evaluations against ground-truth datasets.\n\nBest regards,\nThe FarmIQ Team"
    )

    add_email(
        "2. Venture Funders (Mercy Corps / Novastar)",
        "Seed Funding Inquiry: Scaling Automated Agronomic Infrastructures",
        "Dear Investment Team,\n\nI am preparing deployment logistics for a decentralized precision software pipeline.\n\nLet us schedule basic demonstrations.\n\nBest regards."
    )

    pdf.output("outreach_emails_proposals.pdf")
    print("Successfully exported outreach templates.")

if __name__ == '__main__':
    build_pdf()
