"""Client progress status PDF. Uses real stored state; does not create/edit revisions.

Dependency: reportlab>=4. Exposes build_status_pdf(state, version, feedback, as_of=None).
"""
from __future__ import annotations
import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether, HRFlowable

DARK = colors.HexColor('#073b2b')
GREEN = colors.HexColor('#15803d')
PALE = colors.HexColor('#eaf6ef')
INK = colors.HexColor('#173127')
MUTED = colors.HexColor('#647a70')
BORDER = colors.HexColor('#d9e9df')
AMBER = colors.HexColor('#99670d')
RED = colors.HexColor('#9b3e35')
COMPLETE = ('Approved','Completed')
NEEDS_CLIENT = ('Awaiting client','In review')

styles = {
 'label': ParagraphStyle('is-label',fontName='Helvetica-Bold',fontSize=8,leading=11,textColor=GREEN,spaceAfter=5),
 'title': ParagraphStyle('is-title',fontName='Helvetica-Bold',fontSize=22,leading=26,textColor=DARK,spaceAfter=8),
 'sub': ParagraphStyle('is-sub',fontName='Helvetica',fontSize=9.5,leading=14,textColor=MUTED,spaceAfter=8),
 'h': ParagraphStyle('is-h',fontName='Helvetica-Bold',fontSize=12,leading=16,textColor=DARK,spaceBefore=16,spaceAfter=8),
 'head': ParagraphStyle('is-head',fontName='Helvetica-Bold',fontSize=8.4,leading=11,textColor=DARK),
 'cell': ParagraphStyle('is-cell',fontName='Helvetica',fontSize=8,leading=12,textColor=INK),
 'cell_b': ParagraphStyle('is-cell-b',fontName='Helvetica-Bold',fontSize=8.4,leading=11,textColor=DARK),
 'small': ParagraphStyle('is-small',fontName='Helvetica',fontSize=7.4,leading=11,textColor=MUTED),
 'foot': ParagraphStyle('is-foot',fontName='Helvetica',fontSize=8.2,leading=12,textColor=INK),
 'num': ParagraphStyle('is-num',fontName='Helvetica-Bold',fontSize=18,leading=22,textColor=DARK),
}

def txt(s, limit=400):
    s = str(s or '').strip()
    return escape(s[:limit]).replace('\n','<br/>')

def para(text, style='cell'):
    return Paragraph(txt(text), styles[style])

def footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(BORDER)
    canvas.line(19*mm, 17*mm, width-19*mm, 17*mm)
    canvas.setFont('Helvetica', 7.3)
    canvas.setFillColor(MUTED)
    canvas.drawString(19*mm, 12.5*mm, 'ECS  |  ISAZI HERBAL SHOP  |  CONFIDENTIAL CLIENT STATUS')
    canvas.drawRightString(width-19*mm, 12.5*mm, f'Page {doc.page}')
    canvas.restoreState()

def build_status_pdf(state: dict, version: int, feedback: list[dict], as_of: datetime|None=None) -> bytes:
    steps = state.get('client_steps', [])
    designs = state.get('designs', [])
    as_of = as_of or datetime.now(timezone.utc)
    done = sum(step.get('status') in COMPLETE for step in steps)
    needs = [s for s in steps if s.get('status') in NEEDS_CLIENT]
    active = [s for s in steps if s.get('status') in ('In progress','Blocked')]
    selected = next((d for d in designs if d.get('status') in ('Selected','Approved')), None)
    out = io.BytesIO()
    doc = SimpleDocTemplate(out,pagesize=A4,rightMargin=19*mm,leftMargin=19*mm,topMargin=17*mm,bottomMargin=24*mm,
        title='Isazi Herbal Shop - Client Project Status',author='Executive Communication Services (ECS)')
    story = []
    story.append(Paragraph('ISAZI HERBAL SHOP  /  EXECUTIVE COMMUNICATION SERVICES',styles['label']))
    story.append(Paragraph('Project status report',styles['title']))
    story.append(Paragraph(f"Generated {as_of.strftime('%d %B %Y, %H:%M UTC')} &nbsp; | &nbsp; Plan version {version} &nbsp; | &nbsp; Based on the current project tracker",styles['sub']))
    cards = [
      [Paragraph(str(done)+' / '+str(len(steps)),styles['num']),Paragraph(str(len(needs)),styles['num']),Paragraph(str(len(active)),styles['num'])],
      [para('Steps completed or approved','small'),para('Client review / decision','small'),para('Work underway or blocked','small')]
    ]
    t = Table(cards,colWidths=[57*mm]*3,rowHeights=[12*mm,12*mm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),12),('LINEBEFORE',(1,0),(1,-1),0.6,BORDER),('LINEBEFORE',(2,0),(2,-1),0.6,BORDER),('TOPPADDING',(0,0),(-1,0),7)]))
    story.append(t)
    story.append(Paragraph('What needs attention',styles['h']))
    if not needs:
        story.append(para('No steps are currently marked Awaiting client or In review.','cell'))
    else:
        for s in needs:
            detail = f"<b>{txt(s.get('title'),110)}</b> — {txt(s.get('status'),45)}<br/><font color='#647a70'>{txt(s.get('evidence') or s.get('detail'),230)}</font>"
            story.append(Paragraph(detail,styles['cell']))
            story.append(Spacer(1,6))
    story.append(Paragraph('Delivery status — every step',styles['h']))
    data=[[para('#','head'),para('Project step','head'),para('Status','head'),para('Owner / target','head')]]
    for i,s in enumerate(steps,1):
        data.append([para(str(i)),para(s.get('title',''),'cell_b'),para(s.get('status')),para(f"{s.get('owner','')}\n{s.get('target','')}" )])
    table=Table(data,colWidths=[10*mm,68*mm,38*mm,55*mm],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([
      ('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7faf8')]),
      ('LINEBELOW',(0,0),(-1,-1),0.45,BORDER),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    story.append(table)
    # Versioned commercial scope: only ECS issues invoices, outside this portal.
    scope = state.get('commercial_scope')
    if scope is None:
        from state import default_commercial_scope
        scope = default_commercial_scope()
    story.append(Paragraph('Website scope and additional services', styles['h']))
    story.append(Paragraph(f"<b>Scope status:</b> {txt(scope.get('scope_status','Draft for confirmation'),90)}", styles['foot']))
    for key,heading in (
        ('included', 'Included in the development fee'),
        ('excluded', 'Excluded - additional services quoted separately'),
        ('third_party','Third-party and recurring expenses (separate)'),
        ('client_duties','Isazi information and approvals required'),
    ):
        story.append(Spacer(1, 8))
        story.append(Paragraph(f'<b>{heading}</b>', styles['head']))
        for entry in scope.get(key,'').splitlines():
            if entry.strip():
                story.append(Paragraph('&#8226; ' + txt(entry,500), styles['cell']))
                story.append(Spacer(1, 3))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Extra-services quotation and written approval</b>', styles['head']))
    story.append(Paragraph(txt(scope.get('change_control',''), 2500), styles['foot']))
    story.append(Spacer(1, 6))
    story.append(Paragraph('<b>Scope confirmation and commercial arrangements</b>', styles['head']))
    story.append(Paragraph(txt(scope.get('tax_note',''), 2500), styles['small']))
    if scope.get('signoff_reference'):
        story.append(Paragraph('<b>Scope approval reference:</b> ' + txt(scope.get('signoff_reference'),1000), styles['small']))
    story.append(Spacer(1, 6))
    story.append(Paragraph('Website design decision',styles['h']))
    story.append(para(f"Selected or approved concept: {selected['title']} ({selected['status']})." if selected else 'No concept is officially selected yet. The client can preview each concept and record preferences.', 'foot'))
    if designs:
        rows=[[para('Concept','head'),para('Status','head'),para('Recorded notes','head')]]
        for d in designs:
            num=sum(n.get('subject_type')=='design' and n.get('subject_id')==d.get('id') for n in feedback)
            rows.append([para(d.get('title')),para(d.get('status')),para(str(num))])
        dt=Table(rows,colWidths=[83*mm,49*mm,39*mm],repeatRows=1,hAlign='LEFT')
        dt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('LINEBELOW',(0,0),(-1,-1),0.5,BORDER),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(Spacer(1,7)); story.append(dt)
    story.append(Paragraph('Most recent client feedback',styles['h']))
    notes = sorted(feedback,key=lambda x: x.get('created_at',''),reverse=True)[:6]
    if not notes:
        story.append(para('No client feedback has been recorded yet.','foot'))
    for note in notes:
        title = next((x.get('title') for x in (steps if note['subject_type']=='step' else designs) if x.get('id')==note.get('subject_id')), note.get('subject_type',''))
        story.append(Paragraph(f"<b>{txt(title,90)}</b> &nbsp; | &nbsp; {txt(note.get('author'),40)} &nbsp; | &nbsp; {txt(note.get('created_at','')[:16],30)}",styles['cell_b']))
        story.append(para(note.get('comment'), 'cell'))
        story.append(Spacer(1,5))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
