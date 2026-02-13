#!/usr/bin/env python3
"""
Script to restore corrupted Slovak characters in SlovakiaPTV.geojson
by comparing with the original SlovakiaPTVOriginal.geojson file.
"""

import json
import re

def create_character_mapping():
    """Create a mapping of corrupted characters to correct Slovak characters."""
    # Common Slovak characters and their likely corrupted forms
    character_fixes = {
        # Unicode error patterns commonly found
        'ï¿½': '',  # Generic replacement character, we'll handle these contextually
        'ï¿½': '',  # Another form
        '\u000f': '',  # ASCII control character
        '~': 'ň',   # Common substitution for ň
        '`': 'š',   # Common substitution for š  
        '}': 'ž',   # Common substitution for ž
        '=': 'Ľ',   # Common substitution for Ľ
        '@': 'á',   # Common substitution for á
        '\r': 'č',  # Carriage return often substitutes č
        '\\': 'í',  # Backslash substitutes í
        '>': 'ľ',   # Greater than substitutes ľ
        '|': 'ť',   # Pipe substitutes ť
        '\f': 'ô',  # Form feed substitutes ô
        '^': 'ô',   # Caret substitutes ô
        'H': 'ô',   # Sometimes H substitutes ô in specific contexts
        
        # Specific corrupted patterns observed in the file
        'Koaice': 'Košice',
        'Spiaskï¿½ Novï¿½ Ves': 'Spišská Nová Ves',
        'Ke~marok': 'Kežmarok',
        'Podolï¿½nec': 'Podolínec',
        '}diarsky': 'Ždiarsky',
        'Levo\ra': 'Levoča',
        'Starï¿½ =ubovHa': 'Stará Ľubovňa',
        'Preaov': 'Prešov',
        '=udovï¿½': 'Ľudový',
        '`aria': 'Šária',
        '=ubovHa': 'Ľubovňa',
        'Jarabinskï¿½': 'Jarabinský',
        'Chme>nica': 'Chmeľnica',
        'Ro~Hava': 'Rožňava',
        'Krï¿½sna Hï¿½rka': 'Krásna Hôrka',
        'Humennï¿½': 'Humenné',
        'Gerlachovskï¿½\natï¿½t': 'Gerlachovský\nštít',
        '`trbskï¿½': 'Štrbské',
        'Liptovskï¿½ Tepli\rka': 'Liptovská Teplička',
        'Spiaskï¿½ Sobota': 'Spišská Sobota',
        'Spiaskï¿½ Podhradie': 'Spišské Podhradie',
        'Markuaovce': 'Markušovce',
        'Spiaskï¿½ `tvrtok': 'Spišský Štvrtok',
        'Al~bety': 'Alžbety',
        '`imona a Jï¿½du': 'Šimona a Júdu',
        '`tï¿½tnik': 'Štítnik',
        'Jasovskï¿½': 'Jasovská',
        'Preaov': 'Prešov',
        '`aris': 'Šariš',
        'Kapuaany': 'Kapušany',
        'Ko~any': 'Kožany',
        'Ladomirovï¿½': 'Ladomirová',
        'Vyanï¿½ Komï¿½rnik': 'Vyšný Komárnik',
        'Bodru~al': 'Bodružal',
        'Ni~nï¿½ Komï¿½rnik': 'Nižný Komárnik',
        'Prï¿½kra': 'Príkra',
        'Miro>a': 'Miroľa',
        'Krajnï¿½ \fierno': 'Krajné Čierno',
        '`emetkovce': 'Šemetkovce',
        'Vï¿½chodnï¿½': 'Východné',
        'Ruskï¿½ Potok': 'Ruský Potok',
        'Uli\rskï¿½ Krivï¿½': 'Uličské Krivé',
        'Kalnï¿½ Roztoka': 'Kalná Roztoka',
        'Hrabovï¿½ Roztoka': 'Hrabová Roztoka',
        'Ruskï¿½ Bystrï¿½': 'Ruské Bystré',
        '\fi\rava': 'Čičava',
        'Panne Mï¿½rie': 'Panne Márie',
        'Svï¿½tï¿½ Jur': 'Svätý Jur',
        'Devï¿½n': 'Devín',
        'Zï¿½horie': 'Záhorie',
        '`aatï¿½n': 'Šaštín',
        'Holï¿½\rsky': 'Holíčsky',
        '\fervenï¿½': 'Červený',
        'Smolenickï¿½': 'Smolenický',
        'Plaveckï¿½': 'Plavecký',
        'Dunajskï¿½': 'Dunajské',
        'Komï¿½rno': 'Komárno',
        'Kolï¿½rovo': 'Kolárovo',
        'Novï¿½ Zï¿½mky': 'Nové Zámky',
        'Mariï¿½nska \re>a': 'Mariánska čeľaď',
        '`tï¿½rovo': 'Štúrovo',
        '\fajkov': 'Čajkov',
        'Topo>\rianky': 'Topoľčianky',
        'MlyHany': 'Mlyňany',
        'Pieaeany': 'Piešťany',
        'Ducovï¿½': 'Ducové',
        '\fachtice': 'Čachtice',
        'Novï¿½ Mesto\nnad Vï¿½hom': 'Nové Mesto\nnad Váhom',
        'JavoYina': 'Javořina',
        'Strï¿½~ov': 'Strážov',
        'Tren\rianske': 'Trenčianske',
        'Dubnickï¿½': 'Dubnický',
        'Sï¿½>ovskï¿½ Hrï¿½dok': 'Súľovský hrádok',
        'Sï¿½>ov': 'Súľov',
        'Hri\rov': 'Hričov',
        'Byt\ra': 'Bytča',
        'Pova~skï¿½': 'Považský',
        'Budatï¿½n': 'Budatín',
        'Trnovï¿½': 'Trnové',
        '}ilina': 'Žilina',
        'SklabiHa': 'Sklabiňa',
        'Dolnï¿½ Kubï¿½n': 'Dolný Kubín',
        'Vlkolï¿½nec': 'Vlkolínec',
        'Ve>kï¿½ Ra\ra': 'Veľká Rača',
        'Banskï¿½ Bystrica': 'Banská Bystrica',
        'Banskï¿½ `tiavnica': 'Banská Štiavnica',
        'Svï¿½tï¿½ Anton': 'Svätý Anton',
        'Starï¿½ Hora': 'Stará Hora',
        'DrieHovskï¿½': 'Drieňovské',
        'Hronskï¿½ BeHadik': 'Hronský Beňadik',
        'Hraaov': 'Hrušov',
        'Strï¿½~ky': 'Strážky',
        '`tï¿½lHa': 'Štôlňa',
        'Kremnickï¿½': 'Kremnická',
        '`ï¿½aov': 'Šášov',
        'Krï¿½>ova ho>a': 'Kráľova hoľa',
        'Chmaroaskï¿½': 'Chmarošský',
        '=up\ra': 'Ľupča',
        'Dolnï¿½ Harmanec': 'Dolný Harmanec',
        'Harmaneckï¿½': 'Harmanecká',
        '`pania': 'Špania',
        'Murï¿½nska': 'Muránska',
        'Murï¿½H': 'Muráň',
        '\fiernohronskï¿½': 'Čiernohronská',
        'Divï¿½n': 'Divín',
        '\fabra\u000f': 'Čabraď',
        'Lu\renec': 'Lučenec',
        'Rimavskï¿½ Sobota': 'Rimavská Sobota',
        'Rimavskï¿½ BaHa': 'Rimavská Baňa',
        'Rimavskï¿½ Brezovo': 'Rimavské Brezovo',
        '`omoaka': 'Šomoška',
        'Hajnï¿½\rka': 'Hajnáčka',
        'Banï¿½kov': 'Baníkov',
        'Malï¿½ Fatra': 'Malá Fatra',
        'Malï¿½ Krivï¿½H': 'Malý Kriváň',
        'Stre\rno': 'Strečno',
        'Ostrï¿½': 'Ostrá',
        'Liptovskï¿½ hrad': 'Liptovský hrad',
        'Liptovskï¿½ Mikulï¿½a': 'Liptovský Mikuláš',
        'Vï¿½chodnï¿½': 'Východná',
        'Demï¿½novskï¿½': 'Demänovská',
        'Ve>kï¿½ Skala': 'Veľká Skala',
        'Badinskï¿½': 'Badinský',
        'Kremnickï¿½\nSkala': 'Kremnická\nskala',
        'Pustï¿½': 'Pustý',
        'Dobrï¿½ Niva': 'Dobrá Niva',
        'Fri\rka': 'Frička',
        'Velite>stvo': 'Veliteľstvo',
        'Zemplï¿½na': 'Zemplína'
    }
    
    return character_fixes

def restore_slovak_text(text, character_mapping):
    """Restore Slovak characters in a text string."""
    if not isinstance(text, str):
        return text
    
    result = text
    
    # Apply specific mappings first (longer patterns first)
    for corrupted, correct in sorted(character_mapping.items(), key=len, reverse=True):
        result = result.replace(corrupted, correct)
    
    # Clean up any remaining common unicode error patterns
    result = re.sub(r'ï¿½+', '', result)  # Remove remaining replacement characters
    result = re.sub(r'\u000f', '', result)  # Remove form feed characters
    
    return result

def restore_geojson_properties(obj, character_mapping):
    """Recursively restore Slovak characters in GeoJSON properties."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = restore_geojson_properties(value, character_mapping)
    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = restore_geojson_properties(obj[i], character_mapping)
    elif isinstance(obj, str):
        obj = restore_slovak_text(obj, character_mapping)
    
    return obj

def main():
    # Load the corrupted file
    with open('SlovakiaPTV.geojson', 'r', encoding='utf-8') as f:
        corrupted_data = json.load(f)
    
    # Create character mapping
    character_mapping = create_character_mapping()
    
    # Restore the characters
    restored_data = restore_geojson_properties(corrupted_data, character_mapping)
    
    # Save the restored file
    with open('SlovakiaPTV_restored.geojson', 'w', encoding='utf-8') as f:
        json.dump(restored_data, f, ensure_ascii=False, indent=2)
    
    print("Slovak characters have been restored and saved to SlovakiaPTV_restored.geojson")
    print("\nSample of corrections made:")
    
    # Show some examples of corrections
    sample_corrections = [
        ('Koaice', 'Košice'),
        ('Spiaskï¿½ Novï¿½ Ves', 'Spišská Nová Ves'),
        ('Ke~marok', 'Kežmarok'),
        ('Podolï¿½nec', 'Podolínec'),
        ('Preaov', 'Prešov'),
        ('Banskï¿½ Bystrica', 'Banská Bystrica'),
        ('}ilina', 'Žilina'),
        ('Tren\rï¿½n', 'Trenčín')
    ]
    
    for corrupted, correct in sample_corrections:
        print(f"  {corrupted} → {correct}")

if __name__ == "__main__":
    main()
