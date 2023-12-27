from typing import NewType


HTMLStr = NewType('HTMLStr', str)


_toXmlTrans = str.maketrans({
		'<' : '&lt;',
		'>' : '&gt;',
		'"' : '&quot;',
		"'" : '&apos;',
		'&' : '&amp;',
		'\n': '<br/>',
	})

_toXmlTextContentTrans = str.maketrans({
		'<' : '&lt;',
		'>' : '&gt;',
		'&' : '&amp;',
	})

_toXmlAttributeDblQuoteTrans = str.maketrans({
		'"' : '&quot;',
		'<' : '&lt;',
		# '>' : '&gt;',
		'&' : '&amp;',
	})

_toXmlAttributeSingleQuoteTrans = str.maketrans({
		"'" : '&apos;',
		'<' : '&lt;',
		# '>' : '&gt;',
		'&' : '&amp;',
	})


def escapeForXml(text: str) -> HTMLStr:
	return HTMLStr(text.translate(_toXmlTrans))


def escapeForXmlTextContent(text: str) -> HTMLStr:
	return HTMLStr(text.translate(_toXmlTextContentTrans))


def unescapeFromXmlTextContent(xmlText: str) -> str:
	if '&' not in xmlText:
		return xmlText
	else:
		return xmlText\
			.replace('&lt;', '<')\
			.replace('&gt;', '>')\
			.replace('&amp;', '&')


def escapeForXmlAttribute(text: str, singleQuoted: bool = False) -> str:
	if singleQuoted:
		return text.translate(_toXmlAttributeSingleQuoteTrans)
	else:
		return text.translate(_toXmlAttributeDblQuoteTrans)


def unescapeFromXml(xmlText: str) -> str:
	if '&' not in xmlText:
		return xmlText.replace('<br/>;', '\n')
	else:
		return xmlText\
			.replace('<br/>;', '\n')\
			.replace('&lt;', '<')\
			.replace('&gt;', '>')\
			.replace('&quot;', '"')\
			.replace('&apos;', "'")\
			.replace('&amp;', '&')


def unescapeFromXmlAttribute(xmlText: str, singleQuoted: bool = False) -> str:
	if '&' not in xmlText:
		return xmlText
	elif singleQuoted:
		return xmlText\
			.replace('&apos;', "'")\
			.replace('&lt;', '<')\
			.replace('&gt;', '>')\
			.replace('&amp;', '&')
	else:
		return xmlText\
			.replace('&quot;', '"')\
			.replace('&lt;', '<')\
			.replace('&gt;', '>')\
			.replace('&amp;', '&')


__all__ = [
	'HTMLStr',
	'escapeForXml',
	'escapeForXmlTextContent',
	'escapeForXmlAttribute',
	'unescapeFromXml',
]
