"""Einheitliche Hilfetexte für die Streamlit-Oberfläche.

Die Texte basieren auf den Zellkommentaren und Berechnungsannahmen des
Excel-Referenzmodells Rev. 8 und wurden für die Weboberfläche sprachlich
vereinheitlicht. Ziel ist, dass jede Eingabe kurz erklärt:

1. was der Parameter beschreibt,
2. auf welche Bezugsgröße/Einheit er sich bezieht und
3. wie er die Modellrechnung beeinflusst.

Die Hilfetexte sind Erläuterungen zum Rechenmodell, keine rechtliche,
förderrechtliche oder kaufmännische Prüfung eines konkreten Projekts.
"""

HELP = {
    # ------------------------------------------------------------------
    # System / Projekt
    # ------------------------------------------------------------------
    "commissioning_year": (
        "Kalenderjahr, in dem die Anlage in Betrieb geht. Das Jahr wird unter anderem für die "
        "zeitabhängige THG-Quotenlogik verwendet; es verschiebt nicht die eingegebenen 8760-h-Zeitreihen."
    ),
    "project_lifetime_years": (
        "Wirtschaftlicher Betrachtungszeitraum des Projekts. Die Laufzeit beeinflusst Finanzierung, "
        "gemittelte Preisentwicklungen, Stacktausch und mehrere Förder-/Erlösberechnungen."
    ),
    "electrolyzer_power_kw": (
        "Installierte elektrische Nennleistung des Elektrolyseurs. Gemeint ist nur der Elektrolyseur; "
        "Peripherie sowie gegebenenfalls H₂-/O₂-Verdichter werden zur Systemleistung zusätzlich berücksichtigt."
    ),
    "peripheral_power_fraction": (
        "Elektrischer Verbrauch der Peripherie (Balance of Plant) relativ zum Elektrolyseurverbrauch, z. B. "
        "für Wasseraufbereitung, Pumpen oder Hilfsaggregate. Der Wert erhöht Systemleistung und Strombedarf."
    ),
    "min_load_fraction": (
        "Minimale Teillast des gesamten Elektrolyseursystems. Steht in einer Stunde weniger Leistung zur "
        "Verfügung, wird die Anlage für diese Stunde abgeschaltet; ein höherer Wert kann die Volllaststunden senken."
    ),
    "avg_efficiency_h2_per_el": (
        "Nennwirkungsgrad des Elektrolyseurs bezogen auf elektrische Energie zu H₂-Energie. Dies ist keine "
        "Systemeffizienz: Peripherie und Verdichter werden separat berücksichtigt."
    ),
    "stack_lifetime_hours": (
        "Technische Stacklebensdauer in äquivalenten Betriebs-/Volllaststunden. Aus Projektlaufzeit und "
        "Volllaststunden bestimmt das Modell, wie viele Stacktausche erforderlich werden."
    ),
    "degradation_per_year": (
        "Lineare Abnahme des Elektrolyseurwirkungsgrads in Prozentpunkten pro Jahr. Rev. 8 bildet daraus einen "
        "mittleren Wirkungsgrad zwischen Stackwechseln; 1 % bedeutet hier 1 Prozentpunkt pro Jahr."
    ),

    # ------------------------------------------------------------------
    # CAPEX allgemein
    # ------------------------------------------------------------------
    "electrolyzer_invest_eur_per_kw": (
        "Spezifische Investitionskosten des Elektrolyseurs je kW installierter Elektrolyseurleistung. "
        "Dieser Posten bildet den Elektrolyseur selbst ab und ist die Bezugsgröße für mehrere weitere Kosten."
    ),
    "epc_eur_per_kw": (
        "Kosten für Engineering, Procurement & Construction je kW Elektrolyseurleistung, also Planung, "
        "Beschaffung und Errichtung/Integration. Der Betrag wird zusätzlich zu Elektrolyseur und BoP angesetzt."
    ),
    "bop_eur_per_kw": (
        "Investitionskosten der Balance of Plant je kW Elektrolyseurleistung. Dazu zählen Anlagenteile außerhalb "
        "des Elektrolyseurs selbst, z. B. Wasseraufbereitung, Rohrleitungen, Pumpen und Hilfssysteme."
    ),
    "hochbau_eur_per_kw": (
        "Spezifische Hochbaukosten je kW Elektrolyseurleistung, z. B. für Gebäude, Einhausungen oder Zäune."
    ),
    "tiefbau_eur_per_kw": (
        "Spezifische Tiefbaukosten je kW Elektrolyseurleistung, z. B. für Fundamente, Erdarbeiten und "
        "bauliche Erschließung."
    ),
    "individual_specific_eur_per_kw": (
        "Zusätzliche projektspezifische CAPEX je kW Elektrolyseurleistung für Kosten, die in den übrigen "
        "Kategorien nicht enthalten sind. Dieser Baustein wird additiv berücksichtigt."
    ),
    "individual_ely_cost_share": (
        "Zusätzliche projektspezifische CAPEX als Anteil der reinen Elektrolyseur-Investitionskosten. "
        "Dieser Anteil wird zusätzlich zu den individuellen €/kW- und Pauschalkosten angesetzt."
    ),
    "individual_fixed_eur": (
        "Zusätzlicher fixer CAPEX-Betrag für projektspezifische Einmalkosten, unabhängig von der Anlagenleistung."
    ),

    # ------------------------------------------------------------------
    # Abwärme
    # ------------------------------------------------------------------
    "waste_heat_enabled": (
        "Aktivieren, wenn Elektrolyse-/Verdichterabwärme technisch nutzbar gemacht und als Nebenprodukt bewertet "
        "werden soll. Dann werden Systemkosten, nutzbare Wärmemenge und mögliche Erlöse berücksichtigt."
    ),
    "waste_heat_system_eur_per_kw": (
        "Investitionskosten des Systems zur Abwärmenutzung je kW Elektrolyseurleistung, z. B. für Wärmetauscher, "
        "Hydraulik und Einbindung. Wirkt nur bei aktivierter Abwärmenutzung."
    ),
    "waste_heat_price_eur_per_mwh": (
        "Heutiger Verkaufspreis bzw. wirtschaftlicher Wert der nutzbaren Abwärme je MWh. Der Erlös wird mit der "
        "nutzbaren Wärmemenge und der angegebenen Preisentwicklung berechnet."
    ),
    "waste_heat_usable_share": (
        "Anteil der rechnerisch anfallenden Abwärme, der tatsächlich technisch und wirtschaftlich genutzt bzw. "
        "verkauft werden kann. 100 % bedeutet vollständige Nutzung der im Modell ermittelten Wärmemenge."
    ),
    "waste_heat_price_escalation_per_year": (
        "Nominale jährliche Änderung des Abwärmepreises. Wie in Rev. 8 wird daraus ein durchschnittlicher "
        "Verkaufspreis über die Projektlaufzeit gebildet."
    ),

    # ------------------------------------------------------------------
    # Sauerstoff
    # ------------------------------------------------------------------
    "oxygen_enabled": (
        "Aktivieren, wenn der bei der Elektrolyse entstehende Sauerstoff aufbereitet/verdichtet und wirtschaftlich "
        "genutzt werden soll. Dann steigen CAPEX und Stromverbrauch; gleichzeitig kann ein O₂-Erlös entstehen."
    ),
    "oxygen_system_eur_per_kw": (
        "Investitionskosten der Sauerstoffaufbereitung je kW Elektrolyseurleistung. Der Posten wird nur bei "
        "aktivierter Sauerstoffnutzung berücksichtigt."
    ),
    "oxygen_compressor_outlet_pressure_bar": (
        "Zieldruck des Sauerstoffverdichters. Ein höheres Druckverhältnis erhöht die berechnete Verdichterarbeit, "
        "die installierte Systemleistung und den Stromverbrauch."
    ),
    "oxygen_compressor_inlet_pressure_bar": (
        "Druck des Sauerstoffs am Verdichtereintritt. Zusammen mit dem Zieldruck bestimmt er das Druckverhältnis "
        "und damit die Verdichterarbeit."
    ),
    "oxygen_compressor_inlet_temperature_c": (
        "Temperatur des Sauerstoffs am Verdichtereintritt. Sie geht in die ideale Gas-/Verdichterrechnung nach "
        "der Methodik von Excel Rev. 8 ein."
    ),
    "oxygen_compressor_efficiency": (
        "Isentroper Wirkungsgrad des O₂-Kompressors. Niedrigere Wirkungsgrade erhöhen den realen spezifischen "
        "Strombedarf der Verdichtung."
    ),
    "oxygen_price_eur_per_t": (
        "Heutiger Verkaufspreis für aufbereiteten Sauerstoff je Tonne. Das Modell setzt gemäß Rev. 8 eine "
        "Sauerstoffproduktion von 8 kg O₂ je kg H₂ an."
    ),
    "oxygen_price_escalation_per_year": (
        "Nominale jährliche Änderung des Sauerstoffverkaufspreises. Rev. 8 verwendet den daraus gebildeten "
        "Durchschnittspreis über die Projektlaufzeit."
    ),

    # ------------------------------------------------------------------
    # H2-Aufbereitung
    # ------------------------------------------------------------------
    "h2_processing": (
        "Aktivieren, wenn Wasserstoff verdichtet wird. Bei deaktivierter Verdichtung werden stattdessen die "
        "Direktsystemkosten angesetzt; bei Verdichtung kommen Verdichter-CAPEX und -Strombedarf hinzu."
    ),
    "h2_direct_system_eur_per_kw": (
        "Investitionskosten der H₂-Aufbereitung bei direkter Nutzung ohne Verdichtung, bezogen auf die "
        "Elektrolyseurleistung. Das Feld ist nur relevant, wenn die H₂-Verdichtung deaktiviert ist."
    ),
    "compressor_system_eur_per_kw": (
        "Investitionskosten des H₂-Verdichtersystems je kW Elektrolyseurleistung. Der Posten wird nur bei "
        "aktivierter Verdichtung angesetzt."
    ),
    "h2_processed_share": (
        "Anteil der jährlichen H₂-Produktion, der verdichtet werden soll. Dieser Anteil skaliert die Auslegungsleistung "
        "und den Stromverbrauch des H₂-Kompressors."
    ),
    "h2_compressor_outlet_pressure_bar": (
        "Zieldruck des Wasserstoffverdichters. Ein höheres Druckverhältnis erhöht Verdichterarbeit, Systemleistung "
        "und Strombedarf."
    ),
    "h2_compressor_inlet_pressure_bar": (
        "Druck des Wasserstoffs am Verdichtereintritt. Zusammen mit dem Zieldruck bestimmt er das für die "
        "Verdichterarbeit maßgebliche Druckverhältnis."
    ),
    "h2_compressor_inlet_temperature_c": (
        "Temperatur des Wasserstoffs am Verdichtereintritt. Sie wird in der idealen Gas-/Verdichterrechnung nach "
        "Excel Rev. 8 verwendet."
    ),
    "h2_compressor_efficiency": (
        "Isentroper Wirkungsgrad des H₂-Kompressors. Niedrigere Wirkungsgrade erhöhen den realen spezifischen "
        "Strombedarf der Verdichtung."
    ),
    "h2_compressor_work": "Isentrope Verdichterarbeit für Wasserstoff nach der Methodik des Excel-Referenzmodells.",
    "oxygen_compressor_work": "Isentrope Verdichterarbeit für Sauerstoff nach der Methodik des Excel-Referenzmodells.",

    # ------------------------------------------------------------------
    # Batterie
    # ------------------------------------------------------------------
    "battery_enabled": (
        "Aktivieren, wenn ein Batteriespeicher im stündlichen Dispatch berücksichtigt werden soll. Der Speicher kann "
        "Überschüsse aufnehmen und später zur Versorgung des Systems abgeben; Rev. 8 modelliert keine Speicherverluste."
    ),
    "battery_capacity_factor_kwh_per_kw": (
        "Speicherkapazität relativ zur installierten Systemleistung. Ein Wert von 5 kWh/kW entspricht ungefähr "
        "einem 5-Stunden-Speicher; die Kapazität wird aus diesem Faktor und der Systemleistung berechnet."
    ),
    "battery_power_kw": (
        "Maximale elektrische Eingangs-/Ladeleistung der Batterie. Die Entladeleistung wird in der Excel-Methodik "
        "separat durch die installierte Systemleistung begrenzt."
    ),
    "battery_invest_eur_per_kwh": (
        "Spezifische Batterie-Investitionskosten je kWh berechneter Speicherkapazität. Höhere Werte erhöhen die CAPEX "
        "direkt proportional zur Speichergröße."
    ),
    "battery_fixed_eur": (
        "Zusätzliche fixe Batteriekosten, z. B. für Netzanschluss, Steuerung, Gebäude oder projektspezifische "
        "Nebenanlagen. Werden unabhängig von der Speicherkapazität addiert."
    ),
    "battery_capacity_factor": (
        "Faktor zwischen Speicherkapazität und Leistung des Elektrolyseursystems. In Rev. 8 bestimmt die "
        "Systemleistung zugleich die maximale Entladeleistung."
    ),

    # ------------------------------------------------------------------
    # Stack / Finanzierung
    # ------------------------------------------------------------------
    "stack_replacement_share": (
        "Kosten eines Stacktauschs als Anteil der ursprünglichen Elektrolyseur-Investitionskosten. Die Anzahl der "
        "Tausche ergibt sich aus Stacklebensdauer, Projektlaufzeit und Volllaststunden."
    ),
    "stack_cost_degression": (
        "Jährliche Veränderung der Stackersatzkosten bis zum Tauschzeitpunkt. Negative Werte bilden erwartete "
        "Kostensenkungen/Skaleneffekte ab; z. B. −5 %/a reduziert spätere Ersatzkosten."
    ),
    "stack_financing_interest_rate": (
        "Zinssatz für die Finanzierung bzw. Rückstellung der Stackersatzkosten. Das Modell folgt der gesonderten "
        "Stackfinanzierungslogik aus Excel Rev. 8."
    ),
    "debt_share": (
        "Anteil der CAPEX nach CAPEX-Förderung, der mit Fremdkapital finanziert wird. Der verbleibende Anteil wird "
        "automatisch als Eigenkapital behandelt."
    ),
    "debt_interest_rate": (
        "Nominaler jährlicher Fremdkapitalzins. Er wird für die Annuität des fremdfinanzierten CAPEX-Anteils verwendet."
    ),
    "equity_interest_rate": (
        "Kalkulatorischer Eigenkapitalzins zur Abbildung der Opportunitäts- bzw. Renditeanforderung des Eigenkapitals. "
        "Er wird separat vom Fremdkapital annuitätisch berücksichtigt."
    ),
    "corporate_tax_rate": (
        "Unternehmenssteuersatz für die WACC-Kennzahl. Wie in Rev. 8 beeinflusst er den ausgewiesenen WACC, nicht aber "
        "die separat berechneten FK-/EK-Annuitäten und damit nicht direkt den LCOH."
    ),

    # ------------------------------------------------------------------
    # OPEX
    # ------------------------------------------------------------------
    "opex_lump_sum": (
        "Aktivieren, wenn OPEX nicht detailliert, sondern als pauschaler Prozentsatz der CAPEX nach CAPEX-Förderung "
        "berechnet werden sollen. Die detaillierten OPEX-Felder werden dann für OPEX Total nicht verwendet."
    ),
    "lump_sum_share_of_capex": (
        "Pauschale jährliche OPEX als Prozentsatz der CAPEX nach CAPEX-Förderung. Nur wirksam, wenn die pauschale "
        "OPEX-Berechnung aktiviert ist."
    ),
    "lump_sum_escalation_per_year": (
        "Nominale jährliche Preisentwicklung der pauschalen OPEX. Rev. 8 bildet daraus einen mittleren Jahreswert "
        "über die Projektlaufzeit."
    ),
    "maintenance_share_of_capex": (
        "Jährliche Wartungs- und Instandhaltungskosten als Anteil der gesamten CAPEX vor Förderung. Personalkosten "
        "werden in Rev. 8 separat erfasst und sollten hier nicht doppelt enthalten sein."
    ),
    "maintenance_escalation_per_year": (
        "Nominale jährliche Kostenentwicklung für Wartung und Instandhaltung. Daraus wird der durchschnittliche "
        "Jahreswert über die Projektlaufzeit gebildet."
    ),
    "personnel_eur_per_year": (
        "Heutige jährliche Brutto-Personalkosten außerhalb der bereits in Wartung & Instandhaltung enthaltenen "
        "Aufwendungen. Hier den gesamten projektrelevanten Personalaufwand pro Jahr ansetzen."
    ),
    "personnel_escalation_per_year": (
        "Nominale jährliche Entwicklung der Personalkosten. Rev. 8 verwendet den daraus resultierenden "
        "durchschnittlichen Jahreswert über die Projektlaufzeit."
    ),
    "reserve_remaining_plant_share_of_capex": (
        "Jährliche Rückstellung für Ersatzinvestitionen der übrigen Anlage als Anteil der CAPEX vor Förderung. "
        "Stackersatz wird separat berechnet und sollte hier nicht noch einmal enthalten sein."
    ),
    "reserve_decommissioning_share_of_capex": (
        "Jährliche Rückstellung für Rückbau/Stilllegung als Anteil der CAPEX vor Förderung. Sie wird gemeinsam mit "
        "den übrigen Rückstellungen über die Projektlaufzeit preislich fortgeschrieben."
    ),
    "reserve_escalation_per_year": (
        "Nominale jährliche Kostenentwicklung der Rückstellungen für Restanlage und Rückbau."
    ),
    "freshwater_price_eur_per_m3": (
        "Preis für bezogenes Frischwasser je m³. Die Excel-Methodik setzt 18 Liter Frischwasser je kg H₂ an "
        "(9 kg stöchiometrisch × Faktor 2)."
    ),
    "freshwater_treatment_price_eur_per_m3": (
        "Zusätzliche Kosten für die Aufbereitung des Frischwassers je m³, z. B. für Entsalzung oder Reinstwasser. "
        "Sie werden auf dieselbe Frischwassermenge wie der Wasserbezugspreis angewendet."
    ),
    "wastewater_price_eur_per_m3": (
        "Kosten für Abwasser je m³. Rev. 8 setzt dafür 9 Liter Abwasser je kg produziertem H₂ an."
    ),
    "water_escalation_per_year": (
        "Nominale jährliche Entwicklung der Wasser-, Aufbereitungs- und Abwasserkosten. Daraus wird ein mittlerer "
        "Jahreswert über die Projektlaufzeit gebildet."
    ),
    "individual_opex_share_of_capex": (
        "Zusätzliche jährliche projektspezifische OPEX als Anteil der CAPEX vor Förderung, z. B. für nicht separat "
        "abgebildete Betriebs-, Versicherungs- oder Dienstleistungskosten."
    ),
    "individual_opex_escalation_per_year": (
        "Nominale jährliche Entwicklung der individuellen OPEX. Rev. 8 verwendet den mittleren Wert über die Laufzeit."
    ),

    # ------------------------------------------------------------------
    # THG-Quote / weitere Erlöse
    # ------------------------------------------------------------------
    "thg_quote": (
        "Aktivieren, wenn Erlöse aus der THG-Quote angesetzt werden sollen. Die Berechnung folgt der in Rev. 8 "
        "hinterlegten Minderungsquoten- und Anrechnungslogik; reale Förderfähigkeit bitte separat prüfen."
    ),
    "thg_price_eur_per_tco2": (
        "Heutiger Erlöswert je anrechenbarer Tonne CO₂-Minderung. Zusammen mit H₂-Menge, Mobilitätsanteil, "
        "THG-Intensität und Erlösanteil bestimmt er den THG-Jahreserlös."
    ),
    "mobility_share": (
        "Anteil der erzeugten H₂-Menge, der dem Mobilitäts-/Verkehrssektor zugeordnet wird und damit in die "
        "THG-Quotenberechnung eingeht."
    ),
    "thg_revenue_share": (
        "Anteil des berechneten THG-Quotenerlöses, der beim H₂-Erzeuger verbleibt. Bei eigener Vermarktung/Tankstelle "
        "kann dieser Anteil höher sein; bei Erlösteilung entsprechend niedriger."
    ),
    "h2_thg_intensity_kgco2_per_gj": (
        "Angenommene THG-Intensität des grünen Wasserstoffs in kg CO₂-Äq. je GJ. Ein höherer Wert reduziert in der "
        "Rev.-8-Logik die anrechenbare THG-Minderung und damit den Erlös."
    ),
    "thg_price_escalation_per_year": (
        "Nominale jährliche Entwicklung des THG-Quotenpreises. Das Modell bildet daraus den durchschnittlichen "
        "Quotenpreis über die Projektlaufzeit."
    ),
    "balancing_energy": (
        "Aktivieren, wenn ein extern kalkulierter Erlös aus Regelenergie berücksichtigt werden soll. Rev. 8 "
        "simuliert keinen Regelenergiemarkt stündlich, sondern übernimmt einen Jahresbetrag."
    ),
    "balancing_energy_revenue_eur_per_year": (
        "Heutiger erwarteter Jahreserlös aus Regelenergie. Diesen Wert außerhalb des Modells aus Markt-/Betriebsannahmen "
        "ermitteln; er wird nicht aus der stündlichen Fahrweise berechnet."
    ),
    "balancing_energy_escalation_per_year": (
        "Nominale jährliche Entwicklung des Regelenergieerlöses. Rev. 8 bildet daraus den mittleren Jahreserlös über "
        "die Projektlaufzeit."
    ),
    "other_revenues": (
        "Aktiviert zwei frei definierbare zusätzliche Jahreserlöse für Einnahmen, die in den übrigen Kategorien "
        "nicht abgebildet sind. Beide Positionen können getrennt preislich fortgeschrieben werden."
    ),
    "other_revenue_1_eur_per_year": (
        "Erster frei definierbarer zusätzlicher Jahreserlös zum heutigen Preisniveau. Den Posten nur verwenden, "
        "wenn er nicht bereits in Stromhandel, THG, Sauerstoff, Abwärme oder Regelenergie enthalten ist."
    ),
    "other_revenue_1_escalation_per_year": (
        "Nominale jährliche Entwicklung des ersten sonstigen Erlöses."
    ),
    "other_revenue_2_eur_per_year": (
        "Zweiter frei definierbarer zusätzlicher Jahreserlös zum heutigen Preisniveau."
    ),
    "other_revenue_2_escalation_per_year": (
        "Nominale jährliche Entwicklung des zweiten sonstigen Erlöses."
    ),

    # ------------------------------------------------------------------
    # Stromversorgung: PPAs
    # ------------------------------------------------------------------
    "baseload_enabled": (
        "Aktivieren, wenn ein Grundlast-PPA als konstante stündliche Stromquelle berücksichtigt werden soll. "
        "Die angegebene Leistung steht im Modell in jeder Stunde des Jahres zur Verfügung."
    ),
    "baseload_kw": (
        "Maximaler stündlicher Strombezug aus dem Baseload-PPA in kW bzw. kWh pro Stunde. Der Wert ist konstant "
        "und wird vor den weiteren Stromquellen eingesetzt."
    ),
    "baseload_price_eur_per_mwh": (
        "Heutiger Arbeitspreis des Baseload-PPA je bezogener MWh. Stromnebenkosten und Privilegierungen werden "
        "separat im entsprechenden Abschnitt ergänzt."
    ),
    "baseload_price_escalation_per_year": (
        "Nominale jährliche Preisentwicklung des Baseload-PPA. Rev. 8 bildet aus Ausgangspreis und Steigerung einen "
        "durchschnittlichen Preis über die Projektlaufzeit."
    ),
    "ppa_pv_enabled": (
        "Aktivieren, wenn ein PV-PPA nach Erzeugungsprofil ('pay as produced') berücksichtigt werden soll. Die "
        "stündliche Verfügbarkeit ergibt sich aus PV-Profil × installierter PPA-Leistung."
    ),
    "ppa_pv_capacity_kw": (
        "Vertraglich zugeordnete PV-Leistung. Das normierte PV-Profil (0…1) wird stündlich mit dieser Leistung "
        "multipliziert und ergibt die verfügbare PPA-Energie."
    ),
    "ppa_pv_price_eur_per_mwh": (
        "Heutiger Arbeitspreis des PV-PPA je gelieferter MWh. Stromnebenkosten werden separat berücksichtigt."
    ),
    "ppa_wind_enabled": (
        "Aktivieren, wenn ein Wind-PPA nach Erzeugungsprofil ('pay as produced') berücksichtigt werden soll. Die "
        "stündliche Verfügbarkeit ergibt sich aus Windprofil × installierter PPA-Leistung."
    ),
    "ppa_wind_capacity_kw": (
        "Vertraglich zugeordnete Windleistung. Das normierte Windprofil (0…1) wird stündlich mit dieser Leistung "
        "multipliziert."
    ),
    "ppa_wind_price_eur_per_mwh": (
        "Heutiger Arbeitspreis des Wind-PPA je gelieferter MWh. Stromnebenkosten werden separat berücksichtigt."
    ),
    "ppa_price_escalation_per_year": (
        "Gemeinsame nominale jährliche Preisentwicklung für PV- und Wind-PPA. Rev. 8 bildet daraus mittlere PPA-Preise "
        "über die Projektlaufzeit."
    ),

    # ------------------------------------------------------------------
    # §7 / CO2
    # ------------------------------------------------------------------
    "section7": (
        "Aktiviert den Excel-kompatiblen Strombezug nach §7 Abs. 3 der 37. BImSchV. Stündlich wird geprüft, ob der "
        "Börsenpreis unter der aus CO₂-Preis und Mindestgrenze abgeleiteten Schwelle liegt; die reale rechtliche "
        "Anwendbarkeit wird vom Tool nicht geprüft."
    ),
    "section7_negative_prices": (
        "Legt fest, ob negative Börsenpreise bei der §7-Grenzpreisprüfung als negative Werte verwendet werden. "
        "Deaktiviert werden negative Preise für diese Prüfung auf 0 €/MWh gesetzt."
    ),
    "section7_co2_price_mode": (
        "Wahl der CO₂-Preisquelle für die §7-Grenzpreisberechnung: eine stündliche Jahresreihe oder ein konstanter "
        "eigener Wert für alle 8760 Stunden."
    ),
    "section7_co2_price_eur_per_t": (
        "Konstanter CO₂-Preis je Tonne für alle Stunden, wenn 'Eigener Wert' gewählt ist. Er beeinflusst die "
        "§7-Grenzpreisschwelle über die in Rev. 8 hinterlegte 0,36-Faktor-Logik."
    ),
    "section7_co2_price_escalation_per_year": (
        "Nominale jährliche Entwicklung des CO₂-Preises. Die gemittelte Preisentwicklung wirkt bereits auf die "
        "stündliche §7-Grenzpreisentscheidung."
    ),
    "co2_price_csv": (
        "CSV mit genau 8760 Stundenwerten für den CO₂-Preis. Verwendet wird die erste numerische Spalte; Werte müssen "
        "endlich und nicht negativ sein."
    ),
    "co2_price_text": (
        "Stündliche CO₂-Preisreihe mit genau 8760 Zahlen, eine Zahl pro Zeile. Diese Werte werden bei 'Jahresdaten' "
        "für die §7-Grenzpreisprüfung verwendet."
    ),

    # ------------------------------------------------------------------
    # §13k
    # ------------------------------------------------------------------
    "section13k": (
        "Aktiviert eine stündlich begrenzte Stromquelle nach §13k EnWG ('Nutzen statt Abregeln'). Die verfügbare Menge "
        "kommt aus der Jahresreihe und wird im Dispatch nach PPA/§7 und vor dem normalen Spotbezug eingesetzt."
    ),
    "section13k_price_eur_per_mwh": (
        "Heutiger Arbeitspreis des nach §13k bezogenen Stroms je MWh. Die verfügbare Menge wird separat über die "
        "8760-h-Reihe vorgegeben."
    ),
    "section13k_price_escalation_per_year": (
        "Nominale jährliche Preisentwicklung des §13k-Strompreises. Rev. 8 verwendet den gemittelten Preis über die "
        "Projektlaufzeit."
    ),
    "section13k_csv": (
        "CSV mit genau 8760 Stundenwerten der verfügbaren §13k-Energie in kWh/h. Verwendet wird die erste numerische "
        "Spalte; negative Werte sind nicht zulässig."
    ),
    "section13k_profile_text": (
        "Stündlich verfügbare §13k-Energie mit genau 8760 Werten in kWh/h, eine Zahl pro Zeile. 0 bedeutet, dass in "
        "dieser Stunde kein §13k-Angebot verfügbar ist."
    ),

    # ------------------------------------------------------------------
    # Stromnebenkosten / Privilegierungen
    # ------------------------------------------------------------------
    "power_privileges": (
        "Stromnebenkosten werden für Elektrolyseur und übrige Verbraucher getrennt bewertet. Eine aktivierte "
        "Befreiung setzt den jeweiligen Kostenbestandteil im Modell auf 0; die tatsächliche Anspruchsberechtigung "
        "muss außerhalb des Rechners geprüft werden."
    ),
    "grid_fee_ct_per_kwh": (
        "Regulärer Netzentgelt-Satz in ct/kWh vor möglichen Befreiungen. Er wird getrennt auf Elektrolyseur- und "
        "Reststrom angewendet, sofern die jeweilige Befreiung nicht aktiviert ist."
    ),
    "electricity_tax_ct_per_kwh": (
        "Regulärer Stromsteuer-Satz in ct/kWh vor möglichen Befreiungen."
    ),
    "concession_fee_ct_per_kwh": (
        "Regulärer Satz der Konzessionsabgabe in ct/kWh vor möglichen Befreiungen."
    ),
    "kwk_levy_ct_per_kwh": (
        "Regulärer KWK-Umlage-/Aufschlagssatz in ct/kWh vor möglichen Befreiungen."
    ),
    "stromnev19_levy_ct_per_kwh": (
        "Regulärer §19-StromNEV-Umlagesatz in ct/kWh vor möglichen Befreiungen."
    ),
    "offshore_levy_ct_per_kwh": (
        "Regulärer Offshore-Netzumlage-Satz in ct/kWh vor möglichen Befreiungen."
    ),
    "electrolyzer_demand_charge_eur_per_kw_month": (
        "Monatlicher Leistungspreis für die maximale Elektrolyseurleistung in €/kW·Monat. Er wird mit 12 Monaten "
        "annualisiert, sofern keine Befreiung aktiviert ist."
    ),
    "electrolyzer_demand_charge_exempt": (
        "Aktivieren, wenn der Elektrolyseur im betrachteten Fall vom Leistungspreis befreit ist. Dann wird dieser "
        "Kostenbestandteil für den Elektrolyseur auf 0 gesetzt."
    ),
    "rest_demand_charge_eur_per_kw_month": (
        "Monatlicher Leistungspreis für die maximale Leistung der übrigen Verbraucher (Peripherie/Verdichter) in "
        "€/kW·Monat."
    ),
    "rest_demand_charge_exempt": (
        "Aktivieren, wenn die übrigen Verbraucher im betrachteten Fall vom Leistungspreis befreit sind."
    ),

    # ------------------------------------------------------------------
    # Zeitreihen PV / Wind / Spot
    # ------------------------------------------------------------------
    "pv_profile_csv": (
        "CSV mit genau 8760 normierten PV-Stundenwerten zwischen 0 und 1. Verwendet wird die erste numerische Spalte; "
        "1 entspricht der vollen angegebenen PV-PPA-Leistung."
    ),
    "pv_profile_text": (
        "Normiertes PV-Erzeugungsprofil mit genau 8760 Werten zwischen 0 und 1, eine Zahl pro Zeile. Der Wert wird "
        "stündlich mit der PV-PPA-Leistung multipliziert."
    ),
    "wind_profile_csv": (
        "CSV mit genau 8760 normierten Wind-Stundenwerten zwischen 0 und 1. Verwendet wird die erste numerische Spalte."
    ),
    "wind_profile_text": (
        "Normiertes Wind-Erzeugungsprofil mit genau 8760 Werten zwischen 0 und 1, eine Zahl pro Zeile. Der Wert wird "
        "stündlich mit der Wind-PPA-Leistung multipliziert."
    ),
    "spot_purchase_enabled": (
        "Aktivieren, wenn nach PPA, §7, §13k und gegebenenfalls Batterie fehlender Strom am Spotmarkt beschafft werden "
        "darf. Hinweis aus dem Excel-Modell: Ein unspezifischer Spotbezug kann die Einordnung als grüner H₂ beeinflussen."
    ),
    "spot_purchase_price_limit_enabled": (
        "Aktivieren, um Spotstrom nur unterhalb eines Maximalpreises zu kaufen. Die Grenze wird außerdem als obere "
        "Schranke der §7-Grenzpreislogik verwendet."
    ),
    "spot_purchase_price_limit_eur_per_mwh": (
        "Maximaler Spotpreis für den allgemeinen Strombezug. Im normalen Spotbezug kauft das Excel-Modell nur bei "
        "Preisen strikt unter dieser Grenze."
    ),
    "spot_price_escalation_per_year": (
        "Nominale jährliche Entwicklung der Spotpreisreihe. Rev. 8 wendet den gemittelten Faktor bereits vor den "
        "stündlichen Kauf-/Grenzpreisentscheidungen an."
    ),
    "power_sale_enabled": (
        "Aktiviert den Verkauf von Strom, der nach Systemverbrauch und Batterieladung übrig bleibt. Der Verkauf kann "
        "zum stündlichen Spotpreis oder zu einem PPA-Verkaufspreis bewertet werden."
    ),
    "power_sale_mode": (
        "Wahl der Erlösbewertung für Überschussstrom: 'Spotmarkt' nutzt die stündlichen Marktpreise, 'PPA' einen "
        "festen Verkaufspreis. Negative Spotpreise werden einnahmeseitig wie in Rev. 8 auf 0 begrenzt."
    ),
    "ppa_sale_price": (
        "Heutiger PPA-Verkaufspreis für überschüssigen Strom. Er wird nur im Verkaufsmodus 'PPA' verwendet."
    ),
    "ppa_sale_price_eur_per_mwh": (
        "Heutiger PPA-Verkaufspreis für überschüssigen Strom je MWh. Die jährliche Verkaufspreisentwicklung wird "
        "über die Projektlaufzeit gemittelt."
    ),
    "spot_sale_price_escalation_per_year": (
        "Nominale jährliche Entwicklung des Stromverkaufspreises. Die Excel-Logik verwendet diese Entwicklung sowohl "
        "im Spot- als auch im PPA-Verkaufsmodus."
    ),
    "spot_sale_price_limit_enabled": (
        "Optionale Erweiterung der Streamlit-App: Überschussstrom wird am Spotmarkt nur verkauft, wenn der Preis "
        "mindestens die angegebene Grenze erreicht. Excel Rev. 8 besitzt diese Zusatzgrenze nicht."
    ),
    "spot_sale_min_price_eur_per_mwh": (
        "Mindestpreis für den optional begrenzten Spotverkauf. Unterhalb dieses Werts bleibt der Überschuss im Modell "
        "unverkauft; diese Funktion ist eine Streamlit-Erweiterung gegenüber Rev. 8."
    ),
    "spot_price_csv": (
        "CSV mit genau 8760 Day-Ahead-Spotpreisen in €/MWh. Verwendet wird die erste numerische Spalte; negative Preise "
        "sind zulässig."
    ),
    "spot_price_text": (
        "Day-Ahead-Spotpreisreihe mit genau 8760 Werten in €/MWh, eine Zahl pro Zeile. Sie beeinflusst Spotbezug, "
        "§7-Prüfung und gegebenenfalls den Überschussverkauf."
    ),

    # ------------------------------------------------------------------
    # Förderungen / SPK
    # ------------------------------------------------------------------
    "capex_subsidy": (
        "Wählt die CAPEX-Förderung: keine, prozentual auf die CAPEX vor Förderung oder als fixer €/kW-Betrag. Die "
        "Förderung reduziert direkt die zu finanzierenden CAPEX."
    ),
    "capex_subsidy_percentage": (
        "Förderquote als Prozentsatz der gesamten CAPEX vor Förderung. 20 % bedeutet, dass 20 % der Brutto-CAPEX "
        "abgezogen und nicht über FK/EK finanziert werden."
    ),
    "capex_subsidy_absolute_eur_per_kw": (
        "Absolute CAPEX-Förderung je kW Elektrolyseurleistung. Der Gesamtbetrag ist Förderwert × installierte "
        "Elektrolyseurleistung."
    ),
    "opex_subsidy": (
        "Wählt die OPEX-Förderung nach produziertem kg H₂ oder je äquivalenter Volllaststunde. Besonderheit Rev. 8: "
        "Im detaillierten OPEX-Modus wird sie ausgewiesen, aber nicht von OPEX Total/LCOH abgezogen."
    ),
    "opex_subsidy_eur_per_kg_h2": (
        "OPEX-Förderbetrag je produziertem kg H₂. Der Jahresbetrag skaliert direkt mit der H₂-Produktion."
    ),
    "opex_subsidy_eur_per_full_load_hour": (
        "OPEX-Förderbetrag je äquivalenter Volllaststunde. Der Jahresbetrag ist Förderwert × Volllaststunden."
    ),
    "electricity_subsidy": (
        "Wählt die Strompreisförderung je kg H₂ oder je MWh Systemstromverbrauch. Der berechnete Jahresbetrag wird "
        "direkt von den Stromkosten abgezogen."
    ),
    "electricity_subsidy_eur_per_kg_h2": (
        "Strompreisförderung je produziertem kg H₂. Der Jahresbetrag skaliert mit der H₂-Produktion."
    ),
    "electricity_subsidy_eur_per_mwh": (
        "Strompreisförderung je tatsächlich verbrauchter MWh Systemstrom (nicht je beschaffter MWh)."
    ),
    "spk": (
        "Wählt die Strompreiskompensation: keine, Berechnung nach der in Rev. 8 hinterlegten Rechnerlogik oder ein "
        "separat kalkulierter Jahresertrag. Die reale Förderfähigkeit wird nicht geprüft."
    ),
    "spk_eua_price_eur_per_tco2": (
        "Heutiger EUA-/Emissionszertifikatspreis je Tonne CO₂ für die SPK-Rechnerlogik. Die gewählte Preisentwicklung "
        "wird über die Projektlaufzeit gemittelt."
    ),
    "spk_power_consumption_factor": (
        "Anteil/Faktor des Systemstromverbrauchs, der in der SPK-Rechnerlogik als förderfähig angesetzt wird. 0,8 "
        "entspricht 80 % des jährlichen Systemstromverbrauchs."
    ),
    "spk_price_escalation_per_year": (
        "Nominale jährliche Entwicklung des EUA-Preises bzw. des separat angesetzten SPK-Ertrags. Rev. 8 bildet "
        "daraus einen Mittelwert über die Projektlaufzeit."
    ),
    "spk_separate_revenue_eur_per_year": (
        "Extern ermittelter heutiger Jahresbetrag der Strompreiskompensation. Wird nur im Modus 'Separat' verwendet."
    ),

    # ------------------------------------------------------------------
    # Sensitivitätsanalyse
    # ------------------------------------------------------------------
    "sensitivity_range_percent": (
        "Prozentuale Abweichung nach unten und oben für die Sensitivitätsanalyse. ±30 % entspricht dem Standard des "
        "Excel-Blatts; der Bereich gilt für Tornado-Diagramm, Tabelle und Detailkurve."
    ),
    "sensitivity_points": (
        "Anzahl der Stützstellen der Detailkurve. 13 Punkte bei ±30 % ergeben 5-%-Schritte von −30 % bis +30 % "
        "einschließlich des Basisfalls."
    ),
    "sensitivity_parameter": (
        "Parameter, dessen LCOH-Verlauf als Detailkurve gezeigt wird. Die übrigen Modellgrößen bleiben gemäß der "
        "Excel-Sensitivitätsmethodik auf dem Basisfall."
    ),

    # ------------------------------------------------------------------
    # Generische Texte / Rückwärtskompatibilität
    # ------------------------------------------------------------------
    "price_escalation": (
        "Nominale jährliche Preisänderung. Excel Rev. 8 diskontiert keine einzelnen Jahreswerte, sondern bildet aus "
        "Ausgangswert und jährlicher Entwicklung einen durchschnittlichen nominalen Wert über die Projektlaufzeit."
    ),
}

# Aliase für UI-Keys, deren Bezeichnung historisch von den semantischen
# Hilfetext-Schlüsseln abweicht. So kann die Oberfläche überall konsequent
# ``HELP[<session_state_key>]`` verwenden.
HELP.update({
    "compression_enabled": HELP["h2_processing"],
    "stack_replacement_share_of_ely_capex": HELP["stack_replacement_share"],
    "stack_cost_degression_per_year": HELP["stack_cost_degression"],
    "lump_sum_enabled": HELP["opex_lump_sum"],
    "thg_enabled": HELP["thg_quote"],
    "balancing_energy_enabled": HELP["balancing_energy"],
    "other_revenues_enabled": HELP["other_revenues"],
    "section7_enabled": HELP["section7"],
    "section7_include_negative_prices": HELP["section7_negative_prices"],
    "section13k_enabled": HELP["section13k"],
    "spot_sale_enabled": HELP["power_sale_enabled"],
    "power_sale_mode": HELP["power_sale_mode"],
    "capex_subsidy_mode": HELP["capex_subsidy"],
    "opex_subsidy_mode": HELP["opex_subsidy"],
    "electricity_subsidy_mode": HELP["electricity_subsidy"],
    "spk_mode": HELP["spk"],
})
