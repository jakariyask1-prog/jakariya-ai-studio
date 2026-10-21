"""Phonetic intelligence and speech normalization engine for bilingual (Bangla & English) STT and TTS.

Ensures accurate speech-to-text spelling (fixing Whisper/Google STT phonetic grapheme errors)
and natural, flawless text-to-speech pronunciation across English and Bengali voices.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# ---------------------------------------------------------------------------
# 1. BENGALI PHONETIC & ORTHOGRAPHIC NORMALIZATION (STT Transcript Fixes)
# ---------------------------------------------------------------------------
# Corrects common Whisper and Google STT phonetic confusions, dialectal
# transcriptions, and split grapheme clusters into standard Bengali orthography.
_BENGALI_PHONETIC_RULES: Final[list[tuple[re.Pattern, str]]] = [
    # Common greetings & inquiries
    (re.compile(r"(?<![^\s\.\?!,।])(?:কেমোন|ক্যমন|ক্যামন|কেমনো)(?![^\s\.\?!,।])"), "কেমন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:অছেন|আছোন|আচেন|আসেন)(?![^\s\.\?!,।])"), "আছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:আছকের|অচকের|আজকার|আচকে|আজকেকার)(?![^\s\.\?!,।])"), "আজকের"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:আজকে|আজকার|আচকে)(?=[,\s\.\?!।]|$)"), "আজকে"),

    # Weather & Nature
    (re.compile(r"(?<![^\s\.\?!,।])(?:আবো\s*হাওয়া|আবো\s*হাওয়া|আবো\s*হো|আবো\s*হাও|আবোহাওয়া|আবোহাওয়া|আবোহ|আবভাও|আবহাও|আবহাওয়া|আপ\s*বহও|আপবহও)(?![^\s\.\?!,।])"), "আবহাওয়া"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:তাপমাত্র|তাপমাত্রাটা)(?![^\s\.\?!,।])"), "তাপমাত্রা"),

    # Common verbs in various inflections (honoric & casual)
    (re.compile(r"(?<![^\s\.\?!,।])(?:করচেন|করসেন)(?![^\s\.\?!,।])"), "করছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:করচি|করসি)(?![^\s\.\?!,।])"), "করছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:করচিস|করসিস)(?![^\s\.\?!,।])"), "করছিস"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:করচো|করসো)(?![^\s\.\?!,।])"), "করছো"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বলচেন|বলসেন)(?![^\s\.\?!,।])"), "বলছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বলচি|বলসি)(?![^\s\.\?!,।])"), "বলছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বলচিস|বলসিস)(?![^\s\.\?!,।])"), "বলছিস"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বলচো|বলসো)(?![^\s\.\?!,।])"), "বলছো"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:চলচেন|চলসেন)(?![^\s\.\?!,।])"), "চলছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:চলচি|চলসি)(?![^\s\.\?!,।])"), "চলছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:আসচেন|আসসেন)(?![^\s\.\?!,।])"), "আসছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:আসচি|আসসি)(?![^\s\.\?!,।])"), "আসছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:যাচ্চেন|জাচ্ছেন|জাচ্চেন)(?![^\s\.\?!,।])"), "যাচ্ছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:যাচ্চি|জাচ্ছি|জাচ্চি)(?![^\s\.\?!,।])"), "যাচ্ছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:হচ্চে|হচে|হইতাছে)(?![^\s\.\?!,।])"), "হচ্ছে"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:দেখচি|দেখসি)(?![^\s\.\?!,।])"), "দেখছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:দেখচেন|দেখসেন)(?![^\s\.\?!,।])"), "দেখছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:শুনচি|শুনসি|সুনছি|সুনসি)(?![^\s\.\?!,।])"), "শুনছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:শুনচেন|শুনসেন|সুনছেন|সুনসেন)(?![^\s\.\?!,।])"), "শুনছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:শুনতে|সুনতে)(?![^\s\.\?!,।])"), "শুনতে"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:পারচি|পারসি)(?![^\s\.\?!,।])"), "পারছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:পারচেন|পারসেন)(?![^\s\.\?!,।])"), "পারছেন"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বুজতে|বুঝতি)(?![^\s\.\?!,।])"), "বুঝতে"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বুজছি|বুজচি|বুজসি)(?![^\s\.\?!,।])"), "বুঝছি"),
    (re.compile(r"(?<![^\s\.\?!,।])(?:বুজছেন|বুজচেন|বুজসেন)(?![^\s\.\?!,।])"), "বুঝছেন"),

    # Common vocabulary & nouns (supporting inflectional suffixes)
    (re.compile(r"ধন্নবাদ"), "ধন্যবাদ"),
    (re.compile(r"সাহাজ্য|সাহাযো"), "সাহায্য"),
    (re.compile(r"বাঙলাদেশ|বাংলদেশ"), "বাংলাদেশ"),
    (re.compile(r"বাংগালী|বাঙ্গালী"), "বাঙালি"),
    (re.compile(r"বাঙলা|বাংল(?!া)"), "বাংলা"),
    (re.compile(r"কস্ট|কোষ্ট"), "কষ্ট"),
    (re.compile(r"সুন্দোর|শুন্দর"), "সুন্দর"),
    (re.compile(r"উচ্চারন"), "উচ্চারণ"),
    (re.compile(r"বানন(?=[^া]|$)"), "বানান"),
    (re.compile(r"ইংরেজী"), "ইংরেজি"),
    (re.compile(r"পরশ্ন|প্রস্শ্ন"), "প্রশ্ন"),
    (re.compile(r"উত্তোর"), "উত্তর"),
    (re.compile(r"বিস্সাস|বিস্বাস"), "বিশ্বাস"),
    (re.compile(r"জ্যাকারিয়া|ঝাকারিয়া"), "জাকারিয়া"),
    (re.compile(r"স্টুডিয়|ষ্টুডিও|ষ্টুডিয়"), "স্টুডিও"),
    (re.compile(r"প্রগ্রামিং|প্রোগ্রামিংগ"), "প্রোগ্রামিং"),
    (re.compile(r"কম্পউটার|কম্পিউটোর"), "কম্পিউটার"),
    (re.compile(r"ইন্টারনট"), "ইন্টারনেট"),
    (re.compile(r"গুরুত্তপূর্ণ|গুরুতপূর্ণ"), "গুরুত্বপূর্ণ"),
    (re.compile(r"দায়িত্ত"), "দায়িত্ব"),
    (re.compile(r"সফটওয়্যার"), "সফটওয়্যার"),
]


# ---------------------------------------------------------------------------
# 2. ENGLISH PHONETIC & COMMON MISSPELLING CORRECTION (STT Transcript Fixes)
# ---------------------------------------------------------------------------
# Corrects frequent speech-to-text recognition errors and non-native pronunciation
# spelling mistakes in English.
_ENGLISH_MISSPELLING_RULES: Final[list[tuple[re.Pattern, str]]] = [
    (re.compile(r"\bpronounciation\b", re.IGNORECASE), "pronunciation"),
    (re.compile(r"\bpronounciations\b", re.IGNORECASE), "pronunciations"),
    (re.compile(r"\bmispel\b|\bmispell\b", re.IGNORECASE), "misspell"),
    (re.compile(r"\bmispelled\b|\bmispeled\b", re.IGNORECASE), "misspelled"),
    (re.compile(r"\bmispelling\b|\bmispeling\b", re.IGNORECASE), "misspelling"),
    (re.compile(r"\bmisspellings\b|\bmispellings\b", re.IGNORECASE), "misspellings"),
    (re.compile(r"\bdebelop\b", re.IGNORECASE), "develop"),
    (re.compile(r"\bdebeloper\b", re.IGNORECASE), "developer"),
    (re.compile(r"\bdebelopment\b", re.IGNORECASE), "development"),
    (re.compile(r"\bbideo\b", re.IGNORECASE), "video"),
    (re.compile(r"\bbideos\b", re.IGNORECASE), "videos"),
    (re.compile(r"\bboyce\b", re.IGNORECASE), "voice"),
    (re.compile(r"\bwether\b", re.IGNORECASE), "weather"),
    (re.compile(r"\bwheather\b", re.IGNORECASE), "weather"),
    (re.compile(r"\btemparature\b", re.IGNORECASE), "temperature"),
    (re.compile(r"\btempreture\b", re.IGNORECASE), "temperature"),
    (re.compile(r"\bcalender\b", re.IGNORECASE), "calendar"),
    (re.compile(r"\btommorow\b", re.IGNORECASE), "tomorrow"),
    (re.compile(r"\btomorow\b", re.IGNORECASE), "tomorrow"),
    (re.compile(r"\bdefinately\b", re.IGNORECASE), "definitely"),
    (re.compile(r"\bdefinitly\b", re.IGNORECASE), "definitely"),
    (re.compile(r"\bseperate\b", re.IGNORECASE), "separate"),
    (re.compile(r"\bseperation\b", re.IGNORECASE), "separation"),
    (re.compile(r"\bneccessary\b", re.IGNORECASE), "necessary"),
    (re.compile(r"\bnecesary\b", re.IGNORECASE), "necessary"),
    (re.compile(r"\brecieve\b", re.IGNORECASE), "receive"),
    (re.compile(r"\brecieves\b", re.IGNORECASE), "receives"),
    (re.compile(r"\brecieved\b", re.IGNORECASE), "received"),
    (re.compile(r"\brecieving\b", re.IGNORECASE), "receiving"),
    (re.compile(r"\buntill\b", re.IGNORECASE), "until"),
    (re.compile(r"\bgrammer\b", re.IGNORECASE), "grammar"),
    (re.compile(r"\benviroment\b", re.IGNORECASE), "environment"),
    (re.compile(r"\bgoverment\b", re.IGNORECASE), "government"),
    (re.compile(r"\bsuccesful\b", re.IGNORECASE), "successful"),
    (re.compile(r"\bpriviledge\b", re.IGNORECASE), "privilege"),
    (re.compile(r"\boccurance\b", re.IGNORECASE), "occurrence"),
    (re.compile(r"\boccured\b", re.IGNORECASE), "occurred"),
    (re.compile(r"\bacomodate\b", re.IGNORECASE), "accommodate"),
    (re.compile(r"\baccommodate\b", re.IGNORECASE), "accommodate"),
    (re.compile(r"\binteligente\b", re.IGNORECASE), "intelligent"),
    (re.compile(r"\bintellgent\b", re.IGNORECASE), "intelligent"),
    (re.compile(r"\bstoodio\b", re.IGNORECASE), "studio"),
    (re.compile(r"\bpithon\b", re.IGNORECASE), "python"),
    (re.compile(r"\bpythan\b", re.IGNORECASE), "python"),
    (re.compile(r"\blangauge\b", re.IGNORECASE), "language"),
    (re.compile(r"\bmessanger\b", re.IGNORECASE), "messenger"),
    (re.compile(r"\bconnetion\b", re.IGNORECASE), "connection"),
    (re.compile(r"\blibary\b", re.IGNORECASE), "library"),
    (re.compile(r"\bresturant\b", re.IGNORECASE), "restaurant"),
    (re.compile(r"\btruely\b", re.IGNORECASE), "truly"),
    (re.compile(r"\bintrest\b", re.IGNORECASE), "interest"),
    (re.compile(r"\bfourty\b", re.IGNORECASE), "forty"),
    (re.compile(r"\bnineth\b", re.IGNORECASE), "ninth"),
    (re.compile(r"\bappologize\b", re.IGNORECASE), "apologize"),
    (re.compile(r"\bapperance\b", re.IGNORECASE), "appearance"),
    (re.compile(r"\barguement\b", re.IGNORECASE), "argument"),
    (re.compile(r"\bbasicly\b", re.IGNORECASE), "basically"),
    (re.compile(r"\bbegining\b", re.IGNORECASE), "beginning"),
    (re.compile(r"\bbeleive\b", re.IGNORECASE), "believe"),
    (re.compile(r"\bcollegue\b", re.IGNORECASE), "colleague"),
    (re.compile(r"\bembarass\b", re.IGNORECASE), "embarrass"),
    (re.compile(r"\bexistance\b", re.IGNORECASE), "existence"),
    (re.compile(r"\bfoward\b", re.IGNORECASE), "forward"),
    (re.compile(r"\bguarentee\b", re.IGNORECASE), "guarantee"),
    (re.compile(r"\bindependant\b", re.IGNORECASE), "independent"),
    (re.compile(r"\bknowlege\b", re.IGNORECASE), "knowledge"),
    (re.compile(r"\bmaintainance\b", re.IGNORECASE), "maintenance"),
    (re.compile(r"\boccurence\b", re.IGNORECASE), "occurrence"),
    (re.compile(r"\bposession\b", re.IGNORECASE), "possession"),
    (re.compile(r"\bpeice\b", re.IGNORECASE), "piece"),
    (re.compile(r"\bprefered\b", re.IGNORECASE), "preferred"),
    (re.compile(r"\brecomended\b", re.IGNORECASE), "recommended"),
    (re.compile(r"\brecommand\b", re.IGNORECASE), "recommend"),
    (re.compile(r"\brefered\b", re.IGNORECASE), "referred"),
    (re.compile(r"\bspeach\b", re.IGNORECASE), "speech"),
    (re.compile(r"\bstrenght\b", re.IGNORECASE), "strength"),
    (re.compile(r"\bsuprise\b", re.IGNORECASE), "surprise"),
    (re.compile(r"\btendancy\b", re.IGNORECASE), "tendency"),
    (re.compile(r"\bthreshhold\b", re.IGNORECASE), "threshold"),
    (re.compile(r"\busefull\b", re.IGNORECASE), "useful"),
    (re.compile(r"\bwierd\b", re.IGNORECASE), "weird"),
    (re.compile(r"\bwritting\b", re.IGNORECASE), "writing"),
]


# ---------------------------------------------------------------------------
# 3. TTS PRONUNCIATION DICTIONARY FOR BENGALI VOICES (English -> Bengali Phonetics)
# ---------------------------------------------------------------------------
# When an English word or technical term is spoken in a Bengali sentence,
# neural TTS engines (like bn-BD-NabanitaNeural or Google TTS bn) either
# spell it letter-by-letter or glitch. Mapping them to authentic Bengali
# phonetic script makes the voice engine articulate them naturally and flawlessly.
_BENGALI_TTS_PHONETIC_VOCAB: Final[dict[re.Pattern, str]] = {
    # AI & Core Tech Acronyms
    re.compile(r"\bAI\b"): "এআই",
    re.compile(r"\bAPI\b"): "এপিআই",
    re.compile(r"\bAPIs\b"): "এপিআই",
    re.compile(r"\bUI\b"): "ইউআই",
    re.compile(r"\bUX\b"): "ইউএক্স",
    re.compile(r"\bURL\b"): "ইউআরএল",
    re.compile(r"\bURLs\b"): "ইউআরএল",
    re.compile(r"\bLLM\b"): "এলএলএম",
    re.compile(r"\bLLMs\b"): "এলএলএম",
    re.compile(r"\bTTS\b"): "টিটিএস",
    re.compile(r"\bSTT\b"): "এসটিটি",
    re.compile(r"\bCPU\b"): "সিপিইউ",
    re.compile(r"\bGPU\b"): "জিপিইউ",
    re.compile(r"\bRAM\b"): "র‌্যাম",
    re.compile(r"\bROM\b"): "রম",
    re.compile(r"\bOS\b"): "ওএস",
    re.compile(r"\bPDF\b"): "পিডিএফ",
    re.compile(r"\bHTML\b"): "এইচটিএমএল",
    re.compile(r"\bCSS\b"): "সিএসএস",
    re.compile(r"\bJS\b"): "জাভাস্ক্রিপ্ট",
    re.compile(r"\bSQL\b"): "এসকিউএল",
    re.compile(r"\bSDK\b"): "এসডিকে",
    re.compile(r"\bID\b"): "আইডি",

    # Common English tech words in Bengali sentences
    re.compile(r"\bPython\b", re.IGNORECASE): "পাইথন",
    re.compile(r"\bStudio\b", re.IGNORECASE): "স্টুডিও",
    re.compile(r"\bJakariya\b", re.IGNORECASE): "জাকারিয়া",
    re.compile(r"\bCode\b", re.IGNORECASE): "কোড",
    re.compile(r"\bCoding\b", re.IGNORECASE): "কোডিং",
    re.compile(r"\bScript\b", re.IGNORECASE): "স্ক্রিপ্ট",
    re.compile(r"\bComputer\b", re.IGNORECASE): "কম্পিউটার",
    re.compile(r"\bInternet\b", re.IGNORECASE): "ইন্টারনেট",
    re.compile(r"\bWebsite\b", re.IGNORECASE): "ওয়েবসাইট",
    re.compile(r"\bSoftware\b", re.IGNORECASE): "সফটওয়্যার",
    re.compile(r"\bHardware\b", re.IGNORECASE): "হার্ডওয়্যার",
    re.compile(r"\bDeveloper\b", re.IGNORECASE): "ডেভেলপার",
    re.compile(r"\bDevelopment\b", re.IGNORECASE): "ডেভেলপমেন্ট",
    re.compile(r"\bProgram\b", re.IGNORECASE): "প্রোগ্রাম",
    re.compile(r"\bProgramming\b", re.IGNORECASE): "প্রোগ্রামিং",
    re.compile(r"\bAssistant\b", re.IGNORECASE): "অ্যাসিস্ট্যান্ট",
    re.compile(r"\bModel\b", re.IGNORECASE): "মডেল",
    re.compile(r"\bPrompt\b", re.IGNORECASE): "প্রম্পট",
    re.compile(r"\bOnline\b", re.IGNORECASE): "অনলাইন",
    re.compile(r"\bOffline\b", re.IGNORECASE): "অফলাইন",
    re.compile(r"\bMessage\b", re.IGNORECASE): "মেসেজ",
    re.compile(r"\bEmail\b", re.IGNORECASE): "ইমেইল",
    re.compile(r"\bGoogle\b", re.IGNORECASE): "গুগল",
    re.compile(r"\bMicrosoft\b", re.IGNORECASE): "মাইক্রোসফট",
    re.compile(r"\bYouTube\b", re.IGNORECASE): "ইউটিউব",
    re.compile(r"\bFacebook\b", re.IGNORECASE): "ফেসবুক",
    re.compile(r"\bGitHub\b", re.IGNORECASE): "গিটহাব",
    re.compile(r"\bFile\b", re.IGNORECASE): "ফাইল",
    re.compile(r"\bFiles\b", re.IGNORECASE): "ফাইল",
    re.compile(r"\bFolder\b", re.IGNORECASE): "ফোল্ডার",
    re.compile(r"\bData\b", re.IGNORECASE): "ডেটা",
    re.compile(r"\bDatabase\b", re.IGNORECASE): "ডাটাবেস",
    re.compile(r"\bUser\b", re.IGNORECASE): "ইউজার",
    re.compile(r"\bPassword\b", re.IGNORECASE): "পাসওয়ার্ড",
    re.compile(r"\bNetwork\b", re.IGNORECASE): "নেটওয়ার্ক",
    re.compile(r"\bSystem\b", re.IGNORECASE): "সিস্টেম",
    re.compile(r"\bServer\b", re.IGNORECASE): "সার্ভার",
    re.compile(r"\bProject\b", re.IGNORECASE): "প্রজেক্ট",
    re.compile(r"\bProblem\b", re.IGNORECASE): "প্রবলেম",
    re.compile(r"\bSolution\b", re.IGNORECASE): "সলিউশন",
    re.compile(r"\bVoice\b", re.IGNORECASE): "ভয়েস",
    re.compile(r"\bAudio\b", re.IGNORECASE): "অডিও",
    re.compile(r"\bVideo\b", re.IGNORECASE): "ভিডিও",
    re.compile(r"\bMicrophone\b", re.IGNORECASE): "মাইক্রোফোন",
    re.compile(r"\bMic\b", re.IGNORECASE): "মাইক",
    re.compile(r"\bSpeaker\b", re.IGNORECASE): "স্পিকার",
    re.compile(r"\bScreen\b", re.IGNORECASE): "স্ক্রিন",
    re.compile(r"\bButton\b", re.IGNORECASE): "বাটন",
    re.compile(r"\bWindow\b", re.IGNORECASE): "উইন্ডো",
    re.compile(r"\bSettings\b", re.IGNORECASE): "সেটিংস",
    re.compile(r"\bVersion\b", re.IGNORECASE): "ভার্সন",
    re.compile(r"\bError\b", re.IGNORECASE): "এরর",
    re.compile(r"\bUpdate\b", re.IGNORECASE): "আপডেট",
    re.compile(r"\bDownload\b", re.IGNORECASE): "ডাউনলোড",
    re.compile(r"\bUpload\b", re.IGNORECASE): "আপলোড",
    re.compile(r"\bApp\b", re.IGNORECASE): "অ্যাপ",
    re.compile(r"\bMobile\b", re.IGNORECASE): "মোবাইল",
    re.compile(r"\bPhone\b", re.IGNORECASE): "ফোন",
    re.compile(r"\bSmart\b", re.IGNORECASE): "স্মার্ট",
    re.compile(r"\bChat\b", re.IGNORECASE): "চ্যাট",
    re.compile(r"\bLive\b", re.IGNORECASE): "লাইভ",
    re.compile(r"\bMode\b", re.IGNORECASE): "মোড",
    re.compile(r"\bTest\b", re.IGNORECASE): "টেস্ট",
    re.compile(r"\bResult\b", re.IGNORECASE): "রেজাল্ট",
    re.compile(r"\bHello\b", re.IGNORECASE): "হ্যালো",
    re.compile(r"\bHi\b", re.IGNORECASE): "হাই",
    re.compile(r"\bBye\b", re.IGNORECASE): "বাই",
    re.compile(r"\bOkay\b|\bOK\b", re.IGNORECASE): "ওকে",
    re.compile(r"\bYes\b", re.IGNORECASE): "হ্যাঁ",
    re.compile(r"\bNo\b", re.IGNORECASE): "না",
    re.compile(r"\bThank you\b|\bThanks\b", re.IGNORECASE): "ধন্যবাদ",
    re.compile(r"\bPlease\b", re.IGNORECASE): "প্লিজ",
    re.compile(r"\bSorry\b", re.IGNORECASE): "স্যরি",
    re.compile(r"\bWelcome\b", re.IGNORECASE): "ওয়েলকাম",
    re.compile(r"\bWeather\b", re.IGNORECASE): "আবহাওয়া",
    re.compile(r"\bTemperature\b", re.IGNORECASE): "তাপমাত্রা",
    re.compile(r"\bPipeline\b", re.IGNORECASE): "পাইপলাইন",
    re.compile(r"\bResponse\b", re.IGNORECASE): "রেসপন্স",
    re.compile(r"\bLatency\b", re.IGNORECASE): "লেটেন্সি",
}


# ---------------------------------------------------------------------------
# Public Functions
# ---------------------------------------------------------------------------

def normalize_stt_transcript(text: str, language: str = "auto") -> str:
    """Correct phonetic and spelling errors in STT transcripts for Bangla and English.

    Cleans noisy acoustic fragments, normalizes spacing, and maps common
    speech-to-text distortions to standard orthography without altering
    native Bengali codepoint representation.
    """
    if not text or not text.strip():
        return ""

    normalized = text

    # Strip raw bracketed acoustic tags e.g. [laughter], (cough), [silence]
    normalized = re.sub(r"\[.*?\]|\(.*?\)", " ", normalized)
    normalized = re.sub(r"[\u200b\ufeff]", "", normalized)

    # Apply Bengali phonetic corrections if Bengali script is detected or requested
    has_bengali = any("\u0980" <= ch <= "\u09ff" for ch in normalized)
    lang_lower = str(language or "").lower()

    if has_bengali or lang_lower.startswith("bn") or lang_lower == "auto":
        for pattern, replacement in _BENGALI_PHONETIC_RULES:
            normalized = pattern.sub(replacement, normalized)

    # Apply English phonetic corrections
    has_english = bool(re.search(r"[a-zA-Z]", normalized))
    if has_english or lang_lower.startswith("en") or lang_lower == "auto":
        for pattern, replacement in _ENGLISH_MISSPELLING_RULES:
            normalized = pattern.sub(replacement, normalized)

    # Final whitespace cleanup
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def normalize_tts_text(text: str, language: str = "auto") -> str:
    """Preprocess text for expressive, accurate neural Text-to-Speech vocalization.

    Handles language-specific phonetics, English loanwords in Bengali speech,
    spelled-out letter sequences, acronyms, currencies, and technical symbols.
    """
    if not text or not text.strip():
        return ""

    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\u09af\u09bc", "\u09df").replace("\u09a1\u09bc", "\u09dc").replace("\u09a2\u09bc", "\u09dd")

    # 1. Expand single-character spelled sequences for clean, individual letter articulation:
    # "P-S-Y-C-H-O-L-O-G-Y" -> "P, S, Y, C, H, O, L, O, G, Y"
    normalized = re.sub(
        r"\b([A-Za-z])(?:-[A-Za-z])+\b",
        lambda m: ", ".join(m.group(0).split("-")),
        normalized,
    )

    # Isolated space-separated uppercase letters (e.g., "A C C O M M O D A T I O N") -> "A, C, C..."
    normalized = re.sub(
        r"(?<=\b[A-Z])\s+(?=[A-Z]\b)",
        ", ",
        normalized,
    )

    # Detect Bengali script context
    has_bengali = any("\u0980" <= ch <= "\u09ff" for ch in normalized)
    is_bn = (str(language).lower().startswith("bn")) or has_bengali

    # 2. Language-specific symbol and acronym expansions
    if is_bn:
        # Currency and symbol expansions in Bengali
        replacements_bn = {
            "৳": " টাকা ",
            "%": " শতাংশ ",
            "$": " ডলার ",
            "&": " এবং ",
            "+": " যোগ ",
            "=": " সমান ",
            "/": " অথবা ",
            "°C": " ডিগ্রি সেলসিয়াস ",
            "°F": " ডিগ্রি ফারেনহাইট ",
            "℃": " ডিগ্রি সেলসিয়াস ",
            "℉": " ডিগ্রি ফারেনহাইট ",
        }
        for char, word in replacements_bn.items():
            normalized = normalized.replace(char, word)

        # Transliterate English tech loanwords into native Bengali script
        # so bn-BD neural voice pronounces them naturally without glitching
        for pattern, replacement in _BENGALI_TTS_PHONETIC_VOCAB.items():
            normalized = pattern.sub(replacement, normalized)

    else:
        # English symbols and abbreviations
        replacements_en = {
            "%": " percent ",
            "$": " dollars ",
            "&": " and ",
            "+": " plus ",
            "=": " equals ",
            "/": " or ",
            "°C": " degrees Celsius ",
            "°F": " degrees Fahrenheit ",
            "℃": " degrees Celsius ",
            "℉": " degrees Fahrenheit ",
        }
        for char, word in replacements_en.items():
            normalized = normalized.replace(char, word)

        # Common abbreviations
        normalized = re.sub(r"\be\.g\.,?\b", "for example, ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bi\.e\.,?\b", "that is, ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bvs\.\b|\bvs\b", "versus", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\betc\.\b|\betc\b", "etcetera", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bDr\.\b", "Doctor ", normalized)
        normalized = re.sub(r"\bMr\.\b", "Mister ", normalized)
        normalized = re.sub(r"\bMrs\.\b", "Missus ", normalized)
        normalized = re.sub(r"\bMs\.\b", "Miss ", normalized)

        # Acronyms with periods for distinct pronunciation
        acronyms = ["AI", "API", "APIs", "UI", "UX", "URL", "URLs", "LLM", "LLMs", "TTS", "STT", "CPU", "GPU", "RAM", "ROM", "OS"]
        for acr in acronyms:
            pattern = rf"\b{acr}\b"
            expanded = ".".join(list(acr)) + "."
            normalized = re.sub(pattern, expanded, normalized)

    # 3. Clean up non-speech punctuation while preserving pauses and Bengali dandas
    normalized = normalized.replace("...", ", ")
    normalized = normalized.replace("—", ", ")
    normalized = normalized.replace("–", ", ")
    normalized = normalized.replace(" - ", ", ")
    normalized = normalized.replace(" : ", ", ")

    # Strip raw markdown and extraneous symbols
    normalized = re.sub(r"[*_~`#^|]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\s*\.\s*", ". ", normalized)

    return normalized.strip()
