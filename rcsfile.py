#!python
# RCSFile class and supporting functions / parsers
# Copyright (C) 2011 Ryan Kavanagh <rak@debian.org>
# 
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

from   pyparsing import *
import pyparsing
import re
import string
import warnings

if pyparsing.__version__ < '1.5.5':
    raise Exception("Needs pyparsing version 1.5.5 or greater")

# Special characters in the RCS file format
special = '$,.:;@'

RCSdigit = Word(nums, min=1, max=1).setName('RCSdigit')
RCSnum = Word(nums + '.').setName('RCSnum')
RCSidchar = ZeroOrMore(string.whitespace) + CharsNotIn(special + string.whitespace).setName('RCSidchar')
RCSid = Combine(
          Optional(".") + RCSidchar + ZeroOrMore(RCSidchar | RCSnum)
        ^ RCSidchar + ZeroOrMore(RCSidchar | RCSnum) )
RCSsym = ZeroOrMore(RCSdigit) + RCSidchar + ZeroOrMore(RCSidchar |
        RCSdigit).setName('RCSsym')
RCSsymbol = Combine(RCSsym + ':' + RCSnum).setName('RCSsymbol')
RCSlocks = (RCSid + ':' + RCSnum).setName('locks')
RCSstring = QuotedString(quoteChar='@', escQuote='@@', multiline=True)

RCSadmin = \
    Keyword('head').suppress() + \
        Optional(RCSnum)('head') + \
        Suppress(';') + \
    Optional(Keyword('branch').suppress() +
        Optional(RCSnum)('branch') +
        Suppress(';')
    ) + \
    Keyword('access').suppress() + \
        Group(ZeroOrMore(RCSid))('access') + \
        Suppress(';') + \
    Keyword('symbols').suppress() + \
        Group(ZeroOrMore(RCSsymbol))('symbols') + \
        Suppress(';') + \
    Keyword('locks').suppress() + \
        Group(ZeroOrMore(RCSlocks))('locks') + \
        Suppress(';') + \
    Optional(Keyword('strict').suppress() +
        Suppress(';')
    ) + \
    Optional(Keyword('comment').suppress() +
        RCSstring.setResultsName('comment') +
        Suppress(';')
    ) + \
    Optional(Keyword('expand').suppress() +
        RCSstring.setResultsName('expand') +
        Suppress(';')
    ) #+ \
    #ZeroOrMore(~RCSdelta + ~RCSdesc + RCSid + ZeroOrMore(RCSid ^ RCSnum ^ RCSstring ^ ':'))

RCSdelta = RCSnum("deltanum") + \
    Keyword('date').suppress() + \
        RCSnum("date") + \
        Suppress(';') + \
    Keyword('author').suppress() + \
        RCSid("author") + \
        Suppress(';') + \
    Keyword('state').suppress() + \
        Optional(RCSid)("state") + \
        Suppress(';') + \
    Keyword('branches').suppress() + \
        Group(ZeroOrMore(RCSnum))("branches") + \
        Suppress(';') + \
    Keyword("next").suppress() + \
        Optional(RCSnum)("next") + \
        Suppress(';') #+ \
    #ZeroOrMore(~RCSdelta + ~Keyword('desc') + RCSid + ZeroOrMore(RCSid ^ RCSnum ^ RCSstring ^ ':'))

RCSdesc = Keyword('desc').suppress() + RCSstring("desc")

RCSdeltatext = RCSnum("deltanum") +\
    Keyword('log') + RCSstring("log") + \
    ZeroOrMore(~Keyword('text') + RCSid + ZeroOrMore(RCSid ^ RCSnum ^ RCSstring ^ ':')) + \
    Keyword('text') + RCSstring("text")

RCStext = RCSadmin("admin") + Group(ZeroOrMore(Group(RCSdelta)))("deltas") + \
          RCSdesc + Group(ZeroOrMore(Group(RCSdeltatext)))("deltatexts")

def test(i):
    try:
        return RCStext.parseString(i)
    except ParseException, pe:
        print pe.markInputline()
        raise pe

def cmp_rcsdates(date1, date2):
    """
    Compares two RCS dates. Accounts for RCS dates being of the form
    YY.mm.dd.HH.MM.SS before 2000 and YYYY.mm.dd.HH.MM.SS afterwards.

    """
    dates = [date1, date2]
    for i, date in enumerate(dates):
        if len(date) == 17:
            dates[i] = '19' + date
    return min(dates)

class RCSFile:
    """
    RCSFile represents RCS files used by the RCS and CVS version control
    systems.

    See rcsfile(5)[http://www.freebsd.org/cgi/man.cgi?query=rcsfile] for
    details on the format.

    If you give us a broken RCS file (for example, more than one
    deltatext with the same delta number and date), we *will* crash and
    burn. You have been warned.

    """

    def __init__(self, lines=None, file=None):
        """ Initialise the object with the lines of an RCS file. """
        if lines and not file:
            parsed = RCStext.parseString(''.join(lines))
            self._filename = '?'
        elif file and not lines:
            parsed = RCStext.parseFile(file)
            if type(file) is str:
                self._filename = file
            elif type(file) is file:
                self._filename = file
            else:
                self._filename = '?'
        else:
            raise ValueError('Either lines or file must be provided')
        # self._lines will contain all lines, newline characters removed
        self._lines = []
        # self._admin will contain the admin block's values
        self._admin = parsed.admin
        # self._symbols will contain tags / symbols
        self._symbols = dict(map(lambda s: s.split(':'),
                                 self._admin.symbols))
        # self._deltas will contain delta blocks
        self._deltas = dict((delta.deltanum, delta)
                            for delta in parsed.deltas)
        # self._deltatexts will contain deltatext blocks
        self._deltatexts = dict((deltatext.deltanum, deltatext)
                            for deltatext in parsed.deltatexts)

    def get_deltanums(self):
        """ Returns a list of all delta numbers. """
        return [d.deltanum for d in self._deltas]

    def get_delta(self, deltanum):
        """ Return metadata about delta delta. """
        try:
            return self._deltas[deltanum]
        except KeyError:
            raise ValueError('Delta %s does not exist.' % delta)

    def get_deltatext(self, deltanum):
        """ Return the deltatext for delta deltanum. """
        try:
            return self._deltatexts[deltanum]
        except KeyError:
            raise ValueError('Delta %s does not exist.' % deltanum)

    def get_head(self):
        """ Return head, or the most revision if unset. """
        if self._admin.head:
            return self._admin.head
        else:
            deltaints = [map(int, d.deltanum.split('.'))
                         for d in self._deltas]
            # We don't want any branches, so the max version X.X
            return '.'.join(max(deltanum for deltanum in deltaints
                                         if len(deltanum) == 2))

    def get_next_tuples(self):
        """
        Returns a list of (deltanum, next) tuples for every
        delta.

        """
        return [(d, self._deltas[d].next) for d in self._deltas]

    def get_ancestor_tuples(self, deltanum):
        """
        Returns a list of ancestors for delta 'deltanum', including
        deltanum, in the format [(delta, next)]

        """
        nexts = self.get_next_tuples()
        ancestors = []
        for i, next in enumerate(nexts):
            if next[0] == deltanum:
                # Probably more effecient that using 'nexts.remove'
                # since we don't have to search the whole list
                ancestors.append(nexts.pop(i))
                break
        # Until there are no more ancestors (next is in the second
        # position of the tuple)
        while ancestors[-1][1]:
            for i, next in enumerate(nexts):
                if next[0] == ancestors[-1][1]:
                    ancestors.append(nexts.pop(i))
                    break
            else:
                # If we get here, it means that we can't find the next
                # delta, the file is screwy.
                warnings.warn("Missing delta: " + deltanum)
                break
        return ancestors

    def get_tags(self, deltanum):
        """
        Returns the tags ('symbols' in RCS lingo) associated with
        deltanum.

        """
        return [x.split(':')[0] for x in self._admin.symbols
                                if x.endswith(':' + deltanum)]

    def get_author(self, deltanum):
        """ Returns the author associated with deltanum. """
        return self._deltas[deltanum]['author']

    def get_date(self, deltanum):
        """ Returns the date associated with deltanum. """
        return self._deltas[deltanum]['date']

    def get_message(self, deltanum):
        """ Returns the commit message associated with deltanum. """
        return self._deltatexts[deltanum]['log']

    def grep(self, pattern, format="rlL", wraplines=False):
        """
        By default, outputs a list of
            (revision, lineno, line)
        where line matches pattern. Line numbering starts at 1.
        Optional argument format determines the output tuple format:
            r ::= revision
            l ::= line number
            L ::= matching line
            a ::= line's author
            d ::= line's date
            D ::= line's date in ISO8601 format: YYYY-MM-DDThh:mm:ssZ
            t ::= line's tags
            f ::= filename
            m ::= commit message

        Approach is as follows:

            1. Set I to the most recent revision, in which the pattern
               occurs. Record its revision, the matching linenos and the
               matching lines.

            2. I = I.next

            3. Copy the record for (I.previous) to I.

            4. Look at the diff of (I+1) and I.
            4.1 Does it delete any lines recorded for I?
            4.1.Y Remove the deleted lines from I's record
            4.2 Does it add any line matching the pattern?
            4.2.Y Add them to I's record
            5. Adjust the line numbers

            6. exists(I.next)?
            6.Y GOTO 2
            6.N return records

        This approach saves us from having to care about uneeded data,
        important when we have a lot to process.

        The wraplines parameter decides whether or not we include the
        next line when the present line ends with a backslash.

        """
        matcher = re.compile(pattern)
        if wraplines:
            wraplines = re.compile(r'.*\\$')
        else:
            # Will never match anything
            wraplines = re.compile('$.^')
        # Matches an insertion command:
        insc = re.compile('a(?P<line>[0-9]+) (?P<lines>[0-9]+)')
        # Matches a deletion command:
        delc = re.compile('d(?P<line>[0-9]+) (?P<lines>[0-9]+)')
        # Various statuses we can be in
        INSERT = 0 # We're in insert mode
        DELETE = 1 # We're in delete mode
        # Where we'll store our matches
        matches = []
        ancestors = self.get_ancestor_tuples(self.get_head())
        for delta in ancestors:
            # Our current status, INSERT or DELETE
            status = None
            # M in (a|d)M N
            startline = None #
            # N in (a|d)M N
            nolines = None
            # We're inserting which line of the current insert block?
            insertline = None
            curr, next = delta
            deletions = []
            insertions = []
            # We must keep track of lines to insert. If we appended
            # lines directly to match, we would get multiple lines
            # associated with a particular line number. Take the command
            # 'a3 2' in a 6 line file. Appending directly to match would
            # give us two lines with lineno 4 and two with lineno 5.
            insertlines = []
            deltatext = self.get_deltatext(curr).text.split('\n')
            # Do we also take the next line?
            takenext = False
            for i, line in enumerate(deltatext, 1):
                # Ommit the last line in head, it's an empty '\n'
                if delta == ancestors[0] and i != len(deltatext):
                    if matcher.match(line) or takenext:
                        matches.append((curr, i, line))
                        if wraplines.match(line):
                            takenext = True
                        else:
                            takenext = False
                    continue
                elif delc.match(line):
                    status = DELETE
                    gd = delc.match(line).groupdict()
                    startline = int(gd['line'])
                    nolines = int(gd['lines'])
                    deletions.append((startline, nolines))
                elif insc.match(line):
                    status = INSERT
                    gd = insc.match(line).groupdict()
                    startline = int(gd['line'])
                    nolines = int(gd['lines'])
                    insertline = 1
                    insertions.append((startline, nolines))
                    continue
                if status == DELETE:
                    matches = [match for match in matches
                            if not (match[0] == curr and
                            startline <= match[1] < startline + nolines)]
                    status = None
                elif status == INSERT:
                    if insertline <= nolines:
                        if matcher.match(line) or takenext:
                            insertlines.append((curr,
                                # Inserts are after startline
                                startline,
                                insertline,
                                line))
                            if wraplines.match(line):
                                takenext = True
                            else:
                                takenext = False
                        insertline += 1
                    else:
                        status = None
            insertions.sort()
            deletions.sort()
            # Delete and insert commands use linenumbers in the
            # original file. We however need to determine the line
            # numbers of the modified file (that in the current
            # delta). Start by looking at all the matches left over
            # after deletions.
            for i, match in enumerate(matches):
                if match[0] == curr:
                    total_insertions = sum(x[1] for x in insertions
                                                if x[0] < match[1])
                    total_deletions = sum(x[1] for x in deletions
                                               if x[0] < match[1])
                    total_adjustment = total_insertions - \
                                       total_deletions
                    matches[i] = (match[0],
                                  match[1] + total_adjustment,
                                  match[2])
            # We can now handle adjusting all those which are insertions
            for i, match in enumerate(insertlines):
                # If match is part of an insertion, the start of which
                # overlapped with a deletion (i.e. d3 2; a3 X), we need
                # to decrement match's line number by 1
                deliter = iter(deletions)
                deliter_val = (-1, -1) # Dummy value for start
                match_overlap = 0
                for ins in insertions:
                    if ins[0] == match[1]:
                        while deliter_val[0] < ins[0]:
                            try:
                                deliter_val = deliter.next()
                            except StopIteration:
                                break
                        if deliter_val[0] == ins[0]:
                            # We have a 'dM N\n aM P', that is, a
                            # deletion and addition that overlap, and
                            # match is one of those additions.
                            match_overlap = 1
                            break
                total_insertions = sum(x[1] for x in insertions
                                            if x[0] < match[1])
                total_deletions = sum(x[1] for x in deletions
                                           if x[0]  < match[1])
                total_adjustment = total_insertions - \
                                   total_deletions - \
                                   match_overlap
                insertlines[i] = (match[0],
                              match[1] + match[2] + total_adjustment,
                              match[3])
            matches.extend(insertlines)
            # We originally had:
            # first_of_curr = min(x[0] for x in enumerate(matches)
            #                         if x[1][0] == curr)
            # but a third of our execution time was spent on it. We
            # know our list is sorted by revision, just count
            # backwards.
            first_of_curr = -1
            for i in range(len(matches) - 1, -1, -1):
                if matches[i][0] == curr:
                    first_of_curr = i
                else:
                    break
            matches[first_of_curr:] = sorted(matches[first_of_curr:])
            if next:
                for match in matches:
                    if match[0] == curr:
                        matches.append((next, match[1], match[2]))
        if format == 'rlL':
            return matches
        else:
            formatted_matches = []
            for match in matches:
                formatted_match = []
                for attr in format:
                    if attr == 'r':
                        formatted_match.append(match[0])
                    elif attr == 'l':
                        formatted_match.append(match[1])
                    elif attr == 'L':
                        formatted_match.append(match[2])
                    elif attr == 'a':
                        formatted_match.append(self.get_author(match[0]))
                    elif attr == 'd':
                        formatted_match.append(self.get_date(match[0]))
                    elif attr == 'D':
                        date = self.get_date(match[0]).split('.')
                        if len(date[0]) == 2:
                            # We have a two digit year.
                            date[0] = '19' + date[0]
                        # Just glue strings together. Saves us many
                        # seconds over using strptime and strftime.
                        formatted_match.append('-'.join(date[:3]) + 'T' +
                            ':'.join(date[3:]) + 'Z')
                    elif attr == 't':
                        formatted_match.append(self.get_tags(match[0]))
                    elif attr == 'f':
                        formatted_match.append(self._filename)
                    elif attr == 'm':
                        formatted_match.append(self.get_message(match[0]))
                    else:
                        raise ValueError("Unknown formatting " +
                                "option %s." % attr)
                formatted_matches.append(tuple(formatted_match))
            return formatted_matches
