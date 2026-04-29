"""
Generate a mock contract PDF for testing the Parser Agent.
Based on the NH-44 Karnataka Road Widening project spec from 01_CONTRACT_PARSER.md.
"""
from fpdf import FPDF
import os


def generate_mock_contract_pdf(output_path: str = "data/mock_contracts/NH44_Karnataka_EPC.pdf"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Cover Page ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 20, "EPC CONTRACT AGREEMENT", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, "4-Laning of NH-44 from Km 220 to Km 260 (40 km)", ln=True, align="C")
    pdf.cell(0, 10, "Contract Type: EPC (NITI Aayog Model)", ln=True, align="C")
    pdf.cell(0, 10, "Contracting Authority: NHAI / Karnataka PWD", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(0, 8, (
        "Contract Value: Rs. 25,00,00,000 (Twenty-Five Crore)\n"
        "Scheduled Construction Period: 730 days (2 years)\n"
        "Agreement Number: NHAI/KA/EPC/2025/001\n"
        "Contractor: XYZ Constructions Pvt. Ltd.\n"
        "Location: NH-44, Karnataka"
    ))

    # ── Article 10 -- Construction Period and Milestones ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "ARTICLE 10 - CONSTRUCTION PERIOD AND MILESTONES", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)

    pdf.multi_cell(0, 7, (
        "Article 10.3.1 The Contractor shall achieve the following Project Milestones:\n\n"
        "Project Milestone-I: The Contractor shall achieve 20% physical progress by the day "
        "falling at 28% of the Scheduled Construction Period (i.e., Day 204 from the Appointed Date). "
        "Liquidated Damages for delay in achieving this milestone shall be levied at the rate of 0.05% "
        "of the apportioned milestone value per day of delay. The Contractor shall be eligible for "
        "catch-up refund if the final Scheduled Completion Date is achieved on time.\n\n"
        "Project Milestone-II: The Contractor shall achieve 50% physical progress by the day "
        "falling at 55% of the Scheduled Construction Period (i.e., Day 401 from the Appointed Date). "
        "Liquidated Damages for delay in achieving this milestone shall be levied at the rate of 0.05% "
        "of the apportioned milestone value per day of delay. The Contractor shall be eligible for "
        "catch-up refund if the final Scheduled Completion Date is achieved on time.\n\n"
        "Project Milestone-III: The Contractor shall achieve 75% physical progress by the day "
        "falling at 75% of the Scheduled Construction Period (i.e., Day 547 from the Appointed Date). "
        "Liquidated Damages for delay in achieving this milestone shall be levied at the rate of 0.05% "
        "of the apportioned milestone value per day of delay. The Contractor shall be eligible for "
        "catch-up refund if the final Scheduled Completion Date is achieved on time.\n\n"
        "Scheduled Completion Date (M4): The Contractor shall achieve 100% physical progress "
        "by Day 730 from the Appointed Date. Liquidated Damages shall be levied at 0.05% of the "
        "total contract price per day. No catch-up refund applies for the final milestone."
    ))

    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Article 10.3.2 - Liquidated Damages", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "Liquidated Damages for delay shall be levied at the rate of 0.05% of the Contract Price "
        "per day of delay. The maximum LD shall not exceed 10% of the Contract Price "
        "(Rs. 2,50,00,000). The LD shall be calculated on the apportioned milestone value for "
        "interim milestones and on the total contract price for the final milestone."
    ))

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Article 10.3.3 - Catch-Up Refund", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "If the Contractor misses an interim milestone but achieves the Scheduled Completion Date "
        "on time, all previously deducted Liquidated Damages for interim milestones shall be "
        "refunded without interest."
    ))

    # ── Article 19 -- Force Majeure ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "ARTICLE 19 - FORCE MAJEURE", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "Article 19.1 The Affected Party shall issue written notice to the other Party within "
        "7 (seven) days of becoming aware of the Force Majeure Event. The notice shall be "
        "addressed to the Authority and the Authority's Engineer. Failure to issue notice "
        "within 7 days forfeits all relief under this Article.\n\n"
        "The notice must contain:\n"
        "(a) A description of the event\n"
        "(b) An assessment of the impact on the project\n"
        "(c) An estimated duration of the event\n"
        "(d) A mitigation strategy\n\n"
        "The Affected Party shall provide weekly updates on the status of the Force Majeure Event.\n\n"
        "Force Majeure categories include: non-political events, indirect political events, "
        "and political events.\n\n"
        "Proof documents required:\n"
        "- Weather events: IMD certified data\n"
        "- Political events: Police FIR or government curfew order\n"
        "- Change in law: Official Gazette notification\n\n"
        "If the Force Majeure Event continues for more than 180 continuous days, either Party "
        "may issue a termination notice."
    ))

    # ── Clause 1 -- Performance Guarantee ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "CLAUSE 1 - PERFORMANCE GUARANTEE", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "The Contractor shall deposit a Performance Guarantee equal to 5% of the Tendered Value "
        "(Rs. 1,25,00,000) within 15 days of the Letter of Acceptance.\n\n"
        "Acceptable forms: Bank Guarantee, Fixed Deposit Receipt (FDR), or Insurance Surety Bond.\n\n"
        "Late submission shall attract a fee of 0.1% per day of delay, up to a maximum extension "
        "of 15 days. If the Performance Guarantee is not submitted within the extended period, "
        "the Letter of Acceptance is deemed cancelled, the Earnest Money Deposit shall be forfeited, "
        "and the contractor shall be debarred."
    ))

    # ── Clause 2 -- Compensation for Delay ──
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "CLAUSE 2 - COMPENSATION FOR DELAY", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "Compensation shall be levied at 1% of the Tendered Value per month (calculated on a "
        "per day basis), subject to a maximum of 10% of the Tendered Value."
    ))

    # ── Clause 2A -- Early Completion Bonus ──
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "CLAUSE 2A - EARLY COMPLETION BONUS", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "If the Contractor completes the work before the Scheduled Completion Date, a bonus of "
        "1% of the Tendered Value per month of early completion shall be paid, subject to a "
        "maximum of 5% of the Tendered Value. The bonus shall be disbursed with the Final Bill only."
    ))

    # ── Clause 5 -- Extension of Time ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "CLAUSE 5 - EXTENSION OF TIME", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "The Contractor must apply for Extension of Time within 14 days of the hindrance.\n\n"
        "The Hindrance Register must be jointly signed by the Contractor and the Junior Engineer "
        "(JE) or Assistant Engineer (AE).\n\n"
        "Overlapping hindrances shall be deducted -- concurrent delays shall not be double-counted.\n\n"
        "If the Contractor fails to apply within 14 days, the right to claim Extension of Time "
        "for that hindrance period is legally forfeited.\n\n"
        "If the Contractor's delay exceeds 90 days beyond the Scheduled Completion Date "
        "(net of approved EoT), this constitutes Contractor Default."
    ))

    # ── Article 23 -- Termination ──
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "ARTICLE 23 - TERMINATION FOR DEFAULT", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "Article 23.1.1 Contractor Default triggers include:\n"
        "(a) Delay beyond the Scheduled Completion Date by more than 90 days (cure period: 60 days)\n"
        "(b) Abandonment of works for more than 15 days (cure period: 60 days)\n"
        "(c) Exhaustion of the LD cap (10% of contract value) (cure period: 60 days)\n"
        "(d) Failure to replenish Performance Security within 15 days (cure period: 15 days)\n\n"
        "Authority Default triggers include:\n"
        "(a) Right of Way not handed over for more than 180 days\n"
        "(b) Payment not released for more than 60 days\n"
        "(c) Work suspended by Authority for more than 180 days\n\n"
        "The Authority shall issue a Notice of Intent to Terminate. The Contractor has a "
        "60-day cure period. If uncured, a Final Termination Notice shall be issued."
    ))

    # ── Article 26 -- Dispute Resolution ──
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "ARTICLE 26 - DISPUTE RESOLUTION", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "Tier 1: Amicable Conciliation -- parties shall attempt to resolve the dispute "
        "amicably within 30 days.\n\n"
        "Tier 2: Arbitration -- if conciliation fails, the dispute shall be referred to a "
        "3-member arbitration tribunal under the Arbitration and Conciliation Act, 1996."
    ))

    # ── Article 11 -- Quality Assurance ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "ARTICLE 11 - QUALITY ASSURANCE", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "Article 11.14 The Contractor shall establish a field laboratory at site.\n\n"
        "The Contractor's tests are primary. The Authority's Engineer shall conduct check tests "
        "on 50% of samples.\n\n"
        "Non-Conformance Reports (NCRs) shall be issued for failed tests. Rectification shall be "
        "on the basis specified by the Authority's Engineer on the NCR.\n\n"
        "Quality tests include:\n"
        "- Concrete: Slump test (every batch, IS:456)\n"
        "- Concrete: Cube strength 7-day and 28-day (1 sample per 1-5 cum, IS:456)\n"
        "- Soil: Field density test (1 per 3000 sqm per layer, MoRTH Section 300)\n"
        "- Bitumen: Bitumen extraction and Marshall test (1 per 400 tonnes, MoRTH Section 500)"
    ))

    # ── Clause 7 -- Payment ──
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "CLAUSE 7 - PAYMENT WORKFLOW", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "The Contractor shall submit the Running Account (RA) Bill by the 5th of each month.\n\n"
        "The Authority's Engineer shall verify the bill within 15 days.\n\n"
        "Payment shall be released within 30 days of verified bill submission.\n\n"
        "Mandatory deductions:\n"
        "- Retention Money: 5%\n"
        "- TDS (Income Tax): 2%\n"
        "- GST TDS: 2%\n"
        "- BOCW Cess: 1%\n"
        "- Liquidated Damages (if applicable): as calculated"
    ))

    # ── Clause 12/13 -- Variation Orders ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "ARTICLE 13 / CLAUSE 12 - VARIATION ORDERS", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, (
        "The total variation in the scope of work shall not exceed 10% of the original "
        "contract value without the Contractor's consent.\n\n"
        "The Contractor must submit a claim notice within 14 days of receiving a variation order.\n\n"
        "Rate basis for existing items: DSR + tender premium/discount.\n"
        "Rate basis for new items: market rate + 15% overhead and profit."
    ))

    # Save
    pdf.output(output_path)
    print(f"[MockContract] PDF generated at {output_path}")
    return output_path


if __name__ == "__main__":
    generate_mock_contract_pdf()
