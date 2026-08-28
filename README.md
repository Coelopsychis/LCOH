# LCOH-Berechnungstool

Ein interaktives Streamlit-Tool zur Berechnung und Analyse der **Wasserstoffgestehungskosten (Levelised Cost of Hydrogen, LCOH)**.

Das Modell kombiniert eine **stündliche Betriebs- und Strommarktberechnung über 8.760 Stunden** mit CAPEX, OPEX, Finanzierung, Stacktausch, Förderungen, Stromnebenkosten und weiteren Erlösen. Dadurch lassen sich unterschiedliche Anlagen-, Beschaffungs- und Vermarktungsszenarien transparent miteinander vergleichen.

## Funktionen

### Technische Modellierung

- Elektrolyseurleistung, Mindestlast und Peripherieverbrauch
- Elektrolyseurwirkungsgrad und jährliche Degradation
- Stacklebensdauer und Stacktausch
- H₂-Aufbereitung und Verdichtung
- Sauerstoffverdichtung und Sauerstofferlöse
- Nutzung und Vermarktung von Abwärme
- optionales Batteriesystem

### Stromversorgung und stündlicher Dispatch

Die Stromversorgung wird stündlich für ein vollständiges Jahr modelliert. Berücksichtigt werden können unter anderem:

- Baseload-PPA
- Pay-as-Produced-PPA für Photovoltaik
- Pay-as-Produced-PPA für Windenergie
- Strombezug nach § 7 Abs. 3 der 37. BImSchV
- Strombezug nach § 13k EnWG
- Batteriespeicher
- Spotmarktbezug
- Überschussvermarktung am Spotmarkt oder zu einem festen PPA-Preis

Für PV, Wind, Spotmarktpreise, CO₂-Preise und §13k-Verfügbarkeit können eigene **8.760-h-Zeitreihen** verwendet werden.

### Kosten und Finanzierung

- Elektrolyseur-CAPEX
- EPC, Balance of Plant, Hoch- und Tiefbau
- individuelle Investitionskosten
- Finanzierung über Fremd- und Eigenkapital
- separate Finanzierung des Stacktauschs
- Wartung und Instandhaltung
- Personalkosten
- Rückstellungen
- Wasserbezug, Wasseraufbereitung und Abwasser
- individuelle OPEX
- jährliche Preissteigerungsraten

### Stromnebenkosten und Privilegierungen

Stromnebenkosten können getrennt für Elektrolyseur und übrige Verbraucher berücksichtigt werden, darunter:

- Netzentgelte
- Stromsteuer
- Konzessionsabgabe
- KWKG-Umlage
- §19-StromNEV-Umlage
- Offshore-Netzumlage
- Leistungspreise

Für einzelne Kostenbestandteile können Befreiungen bzw. Privilegierungen modelliert werden.

> **Hinweis:** Das Tool bildet die rechnerischen Auswirkungen eingegebener Förderungen, Privilegierungen und gesetzlicher Mechanismen ab. Es prüft nicht automatisch, ob im konkreten Projekt ein rechtlicher Anspruch oder eine tatsächliche Berechtigung besteht.

### Förderungen und Erlöse

Unter anderem können berücksichtigt werden:

- CAPEX-Förderung
- OPEX-Förderung
- Strompreisförderung
- Strompreiskompensation (SPK)
- THG-Quotenerlöse
- Stromverkauf
- Sauerstofferlöse
- Abwärmeerlöse
- Regelenergie
- weitere frei definierbare Erlöse

### Ergebnisse und Visualisierung

Das Tool berechnet unter anderem:

- LCOH in €/kg H₂
- LCOH in ct/kWh H₂
- jährliche H₂-Produktion
- äquivalente Volllaststunden
- mittleren Wirkungsgrad
- CAPEX und spezifische CAPEX
- jährliche OPEX
- Finanzierungskosten
- Stacktauschkosten
- Stromkosten und mittlere Strompreise
- Förderungen und Erlöse
- zahlreiche technische und wirtschaftliche Detailkennzahlen

Die Ergebnisse werden zusätzlich in mehreren Plotly-Diagrammen visualisiert.

### Sensitivitätsanalyse

Eine integrierte Sensitivitätsanalyse untersucht den Einfluss zentraler Parameter auf den LCOH:

- THG-Quote
- Zinsen
- OPEX
- Projektlaufzeit
- CAPEX
- Volllaststunden
- Strompreis

Neben einer Tornado-Darstellung kann für jeden Parameter eine Detailkurve berechnet und als CSV exportiert werden.

### Simulationen speichern und laden

Komplette Eingabeszenarien können in der Sidebar als JSON gespeichert und später wieder geladen werden.

Gespeichert werden:

- sämtliche Modellparameter
- alle fünf verwendeten 8.760-h-Zeitreihen

Die Ergebnisse werden beim Laden mit dem aktuellen Modell neu berechnet.

## Installation

### Voraussetzungen

- Python **3.10 oder neuer**
- `pip`

Benötigte Python-Pakete:

- `streamlit`
- `pandas`
- `numpy`
- `plotly`

### Virtuelle Umgebung anlegen

Repository klonen und in den Projektordner wechseln:

```bash
git clone <REPOSITORY-URL>
cd <REPOSITORY-ORDNER>
```

Virtuelle Umgebung erstellen:

```bash
python -m venv .venv
```

Unter Windows aktivieren:

```powershell
.venv\Scripts\activate
```

Unter Linux/macOS aktivieren:

```bash
source .venv/bin/activate
```

Abhängigkeiten installieren:

```bash
python -m pip install --upgrade pip
pip install streamlit pandas numpy plotly
```

## Starten

Die Anwendung wird aus dem Projektverzeichnis gestartet:

```bash
streamlit run app.py
```

Streamlit öffnet die Anwendung anschließend normalerweise automatisch im Browser. Andernfalls kann die im Terminal angezeigte lokale Adresse geöffnet werden.

## Bedienung

Die Eingaben sind in sieben Bereiche gegliedert:

1. **System**
2. **CAPEX**
3. **OPEX**
4. **Strom & Zeitreihen**
5. **Förderungen**
6. **Ergebnisse**
7. **Sensitivität**

Viele Eingabefelder besitzen einen `?`-Hilfetext, der Bedeutung, Bezugsgröße und Wirkung des Parameters im Modell erläutert.

Nach Änderung der Eingaben wird die Simulation über die Schaltfläche **„Berechnung starten“** in der Sidebar ausgeführt.

## Zeitreihen

Das Modell verwendet ein vollständiges Jahr mit **8.760 Stunden**.

Folgende stündliche Reihen werden unterstützt:

| Zeitreihe | Bedeutung |
|---|---|
| `pv_kwh_per_kw` | spezifisches PV-Erzeugungsprofil |
| `wind_kwh_per_kw` | spezifisches Wind-Erzeugungsprofil |
| `day_ahead_eur_per_mwh` | Day-Ahead-Strompreis in €/MWh |
| `co2_eur_per_t` | CO₂-Preis in €/t |
| `section13k_kwh` | verfügbare Energiemenge nach §13k EnWG |

Im Repository liegt mit `reference_timeseries.csv` ein deterministischer Standarddatensatz, der einen reproduzierbaren Ausgangsfall ermöglicht.

Eigene Zeitreihen können über die Oberfläche hochgeladen oder eingefügt werden. Eine vollständige Jahresreihe muss jeweils genau **8.760 Werte** enthalten.

## Export

### Simulation speichern

Über **„Simulation speichern / laden“** in der Sidebar wird ein vollständiges Eingabeszenario als JSON exportiert.

Diese Datei ist für die spätere Wiederherstellung einer Simulation gedacht und enthält keine berechneten Ergebnisse.

### Ergebnisse exportieren

Auf der Ergebnisseite stehen Exporte als:

- CSV
- JSON

zur Verfügung.

Der Ergebnisexport enthält ausschließlich berechnete Ergebnisse und abgeleitete Kennzahlen.

### Sensitivitätskurven exportieren

Die Detailkurve der Sensitivitätsanalyse kann direkt unterhalb des Diagramms als CSV heruntergeladen werden.

Die CSV-Exporte verwenden:

- Semikolon als Spaltentrenner
- Komma als Dezimaltrennzeichen
- UTF-8 mit BOM für eine gute Kompatibilität mit deutschsprachigen Tabellenkalkulationsprogrammen

## Modellansatz

Der LCOH wird aus annualisierten Kosten und Erlösen sowie der jährlichen Wasserstoffproduktion bestimmt.

Vereinfacht:

\[
LCOH =
\frac{
\text{jährliche Investitions- und Finanzierungskosten}
+ \text{OPEX}
+ \text{Stromkosten}
+ \text{Stacktausch}
- \text{Förderungen}
- \text{Erlöse}
}{
\text{jährliche H₂-Produktion}
}
\]

Die Betriebsgrößen werden zuvor aus dem stündlichen Dispatch über 8.760 Stunden bestimmt.

Das Modell arbeitet mit nominalen, über die Projektlaufzeit gemittelten Preisentwicklungen. Es handelt sich nicht um ein vollständiges Discounted-Cashflow-Modell mit jahresscharfen Zahlungsströmen.

## Wichtige Modellgrenzen

Bei der Interpretation der Ergebnisse sollten insbesondere folgende Punkte berücksichtigt werden:

- Das Modell bildet ein repräsentatives Jahr mit 8.760 Stunden ab.
- Die Qualität der Ergebnisse hängt wesentlich von den verwendeten Zeitreihen und Eingabeannahmen ab.
- Preisentwicklungen werden über die Projektlaufzeit modelliert, zukünftige Marktpreise jedoch nicht prognostiziert.
- Rechtliche Voraussetzungen von Förderungen, Abgabenbefreiungen und Privilegierungen werden nicht automatisch geprüft.
- Steuern, Bilanzierung und projektspezifische Vertragsbedingungen werden nur insoweit berücksichtigt, wie sie explizit im Modell abgebildet sind.
- Das Ergebnis ist daher eine **Szenario- und Entscheidungsunterstützung**, keine verbindliche Investitions-, Rechts- oder Steuerberatung.

## Projektstruktur

```text
.
├── app.py                    # Streamlit-Oberfläche
├── help_texts.py             # Hilfetexte der Eingabefelder
├── widgets.py                # wiederverwendbare UI-Komponenten
├── reference_timeseries.csv  # Standard-Zeitreihen für 8.760 Stunden
│
├── core/
│   ├── constants.py          # physikalische und modellweite Konstanten
│   ├── models.py             # Eingabedatenmodelle
│   ├── timeseries.py         # Zeitreihen laden, parsen und validieren
│   ├── simulation.py         # stündlicher Dispatch und Betriebskennzahlen
│   ├── technical.py          # technische Teilmodelle
│   ├── finance.py            # Kosten, Finanzierung, Erlöse und LCOH
│   ├── sensitivity.py        # Sensitivitätsanalyse
│   ├── reporting.py          # Ergebnisaufbereitung und Exporte
│   └── scenario.py           # Speichern und Laden kompletter Simulationen
```