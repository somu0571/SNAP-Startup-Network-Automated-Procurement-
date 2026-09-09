"""
Script to generate sample startup solution documents (DOCX/PDF) for testing the RAG engine.
Run: python create_sample_docs.py
"""
import os

try:
    from docx import Document
except ImportError:
    Document = None

SAMPLE_SOLUTIONS = [
    {
        "filename": "AquaSense_IoT_Solution.docx",
        "content": """AquaSense Technologies Pvt. Ltd.
Outcome-Based Technical & Commercial Proposal for Municipal Pipeline Monitoring

1. Executive Summary & Approach:
AquaSense provides an IoT acoustic sensing & edge AI monitoring system designed specifically for underground municipal water networks. Our non-invasive acoustic sensors clamp directly onto pipeline valves every 400 meters, detecting micro-vibrations and frequency anomalies associated with pressurized pipe leakages. Edge microcontrollers perform Fourier transform acoustic analysis and stream alerts over 4G/NB-IoT to our centralized web dashboard within 90 seconds of breach.

2. Technology Stack:
- Hardware: ESP32 + Piezoelectric acoustic sensors + Solar battery backup
- Edge & Gateway: MQTT protocol, TLS 1.3 encryption, NB-IoT cellular fallback
- Cloud Platform: Python FastAPI, TimescaleDB for time-series sensor data, React dashboard
- Integrations: SCADA OPC-UA integration module already built and certified

3. Technology Readiness Level (TRL):
TRL 7 - System prototype demonstrated in operational environment. Successfully piloted across 45km of pipeline with Pune Municipal Corporation (PMC) in Q3 2023, detecting 14 minor leaks with 92% accuracy.

4. Team Experience & Track Record:
Core team of 8 full-time engineers led by IIT Bombay alumni with 7+ years of industrial automation and embedded telemetry experience. Advisors include ex-Chief Engineer of Maharashtra Water Supply Board.

5. Pilot Readiness & Timeline:
Pilot ready to deploy within 30 days. We maintain an inventory of 200 pre-calibrated sensor units. Deployment for 100km can be operational in 4 weeks.

6. Cost Estimate:
- 100km Pilot Project: Rs 38,50,000 (inclusive of sensors, cloud hosting, installation, and 6 months maintenance).
- Full 500km scaling estimate: Rs 1.65 crore.

7. Claimed Outcomes & KPI Impact:
- Reduction in Non-Revenue Water (NRW) loss by 35% within 9 months.
- Leak detection alert latency reduced from 21 days to under 2 minutes.
- Zero excavation required for sensor mounting.

8. Statutory & Compliance Details:
- DPIIT Recognition: Yes (DIPP Certificate No: DIPP89421)
- Annual Turnover: Rs 2.1 Crore (FY 2023-24)
- Incorporation: 3 years ago (Registered Private Limited Company)
"""
    },
    {
        "filename": "HydroVision_Satellite_Solution.docx",
        "content": """HydroVision Analytics India
Satellite Radar (SAR) & Predictive AI for Pipeline Leakage & Soil Moisture Anomaly

1. Executive Summary & Approach:
HydroVision delivers orbital synthetic aperture radar (SAR) soil saturation analysis combined with pressure gauge telemetry. By analyzing L-band radar backscatter from Sentinel-1 and NISAR satellites, we spot subsurface moisture buildup from pipeline leaks without requiring physical sensor deployment along every meter of pipe.

2. Technology Stack:
- Remote Sensing: Sentinel-1 SAR imagery processing via Google Earth Engine
- AI/ML Models: Convolutional Neural Networks (U-Net) trained on municipal GIS pipe shapefiles
- Backend & Frontend: Node.js, Python FastAPI, Mapbox GL JS spatial interface
- Integration: RESTful GeoJSON API for GIS/SCADA integration

3. Technology Readiness Level (TRL):
TRL 6 - Technology demonstrated in relevant environment. Completed validation study on 80km canal and pipeline corridor with Gujarat Water Infrastructure Ltd.

4. Team Experience:
Founders hold PhDs in Geoinformatics from ISRO/IIRS with 6 years experience in spatial analytics and satellite remote sensing.

5. Pilot Readiness & Timeline:
Can initiate satellite baseline survey within 15 days of receiving pipeline GIS vector data. Requires zero on-ground hardware setup.

6. Cost Estimate:
- Pilot (500km coverage for 6 months): Rs 28,00,000.
- Annual recurring monitoring subscription: Rs 45,00,000/year.

7. Claimed Outcomes:
- Pinpoint leak zones to within 10-meter precision radius.
- Detect invisible underground leaks 2-3 weeks before surfacing.
- Whole-city pipeline network coverage refreshed every 6 days.

8. Statutory & Compliance Details:
- DPIIT Recognition: Yes (DIPP Certificate No: DIPP67114)
- Annual Turnover: Rs 95 Lakhs (FY 2023-24)
- Incorporation: 2 years ago
"""
    },
    {
        "filename": "MegaCorp_Ineligible_Sample.docx",
        "content": """MegaInfrastructure Solutions Ltd.
Proposal for Pipeline Modernization & Traditional Valve Replacement

1. Executive Summary:
MegaInfrastructure proposes full physical excavation and replacement of municipal ductile iron pipelines with fiber-reinforced polymer pipes and manual pressure check valves.

2. Technology Stack:
Conventional hydraulic pressure testing, excavation earthmovers, manual valve gauges.

3. Technology Readiness:
TRL 9 - Commercial off the shelf heavy civil works.

4. Team:
3,500 construction workers and civil engineers.

5. Cost Estimate:
Rs 45.0 Crore.

6. Statutory & Compliance Details:
- DPIIT Recognition: No (Large Enterprise, not a startup)
- Annual Turnover: Rs 850 Crore (FY 2023-24)
"""
    }
]

def generate_samples():
    out_dir = os.path.join(os.path.dirname(__file__), "sample_docs")
    os.makedirs(out_dir, exist_ok=True)

    for item in SAMPLE_SOLUTIONS:
        filename = item["filename"]
        filepath = os.path.join(out_dir, filename)
        
        if Document is not None and filename.endswith(".docx"):
            doc = Document()
            for para in item["content"].strip().split("\n\n"):
                doc.add_paragraph(para.strip())
            doc.save(filepath)
            print(f"Generated DOCX: {filepath}")
        else:
            # Fallback to txt/docx text
            txt_path = filepath.replace(".docx", ".txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(item["content"])
            print(f"Generated text: {txt_path}")

if __name__ == "__main__":
    generate_samples()
