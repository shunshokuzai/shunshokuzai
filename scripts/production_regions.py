"""Source allocation from official crop statistics and seasonal origin shares."""
import datetime as dt,io,json,re,unicodedata,urllib.parse,urllib.request
from bs4 import BeautifulSoup
import openpyxl
from update_data import BASE,now_iso,ALIASES
from market_history import atomic_text
PATH=BASE/'data/source_regions.json'
VEG='https://www.maff.go.jp/j/tokei/kouhyou/sakumotu/sakkyou_yasai/'
PREFS='北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄'.split()
def compact(x):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(x or '')))
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 official production plan'}),timeout=25) as r:
  raw=r.read(6_000_001)
 if len(raw)>6_000_000:raise ValueError('Production source too large')
 return raw
def vegetable_profiles(raw,url,foods):
 wb=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True);out={}
 names={f['name'] for f in foods}
 for sh in wb.worksheets:
  name=ALIASES.get(compact(sh.title),compact(sh.title))
  if name not in names or name in ('やまのいも',):continue
  rows=list(sh.iter_rows(values_only=True));header=next((r for r in rows[:15] if '収穫量' in [compact(x) for x in r] and '出荷量' in [compact(x) for x in r] and any('都道府県' in compact(x) for x in r)),None)
  if not header:continue
  col=[compact(x) for x in header].index('収穫量')
  year_match=re.search(r'令和(\d+)年産',''.join(compact(x) for r in rows[:8] for x in r if x))
  if not year_match:continue
  year=2018+int(year_match[1]);values=[];national=None
  for row in rows:
   place=compact(row[1]) if len(row)>1 else '';v=row[col] if len(row)>col else None
   if isinstance(v,bool) or not isinstance(v,(int,float)) or v<=0:continue
   if place=='全国':national=v
   if place in PREFS:values.append((place,v))
  if len(values)<3 or not national:continue
  values.sort(key=lambda x:x[1],reverse=True)
  out[name]={'basis':f'{year}年産・{sh.title}の都道府県別収穫量上位3県（過年度の産地構成）','year':year,'regions':[{'name':n,'share':round(v/national*100,1),'harvestTonnes':v} for n,v in values[:3]],'sourceUrl':url}
 return out
def prepare_plan(obj,today,getter=get,path=PATH):
 state=json.loads(path.read_text(encoding='utf-8'));warnings=[]
 previous=state.get('vegetableCheckedAt','')
 if not previous or (today-dt.date.fromisoformat(previous)).days>=30:
  try:
   soup=BeautifulSoup(getter(VEG),'html.parser')
   link=next((a for a in soup.select('a[href]') if 'files/data?' in a['href'] and 'e-stat.go.jp' in a['href']),None)
   if link is None:raise ValueError('Latest crop workbook link missing')
   url=link['href'];profiles=vegetable_profiles(getter(url),url,obj['foods'])
   if len(profiles)<15:raise ValueError('Too few verified production profiles')
   state['profiles'].update(profiles);state['vegetableCheckedAt']=today.isoformat()
   state['vegetableSourceUrl']=url
   atomic_text(path,json.dumps(state,ensure_ascii=False,indent=2)+'\n')
  except Exception as e:warnings.append(type(e).__name__+': '+str(e)[:160])
 plans={}
 for f in obj['foods']:
  parent={'シャインマスカット':'ぶどう','巨峰':'ぶどう','栗かぼちゃ':'かぼちゃ','いちご（夏秋）':'いちご','いんげん':'さやいんげん'}.get(f['name'],f['name'])
  plan=dict(state['profiles'].get(parent,{}))
  if parent!=f['name'] and plan:plan['basis']+='。'+parent+'全体の参考値であり品種別順位ではありません'
  plans[f['id']]={**plan,'regions':plan.get('regions',[]),'checkedAt':now_iso()}
 obj['metadata']['foodSourcePlan']=plans
 obj['metadata']['sourcePlanningWarnings']=warnings
 obj['metadata']['sourcePlanningProfileCount']=sum(bool(x['regions']) for x in plans.values())
 return plans
def monthly_origins(obj,html,url):
 plans=obj['metadata'].setdefault('foodSourcePlan',{});soup=BeautifulSoup(html,'html.parser')
 for table in soup.select('table'):
  head=compact(table.get_text())
  if '主産地' not in head or '入荷シェア' not in head:continue
  period=re.search(r'令和(\d+)年(\d+)月',head)
  for row in table.select('tr'):
   cells=[compact(c.get_text()) for c in row.find_all(['td','th'],recursive=False)]
   if len(cells)<3:continue
   name=ALIASES.get(cells[0],cells[0]);food=next((f for f in obj['foods'] if f['name']==name),None)
   if not food:continue
   regions=[{'name':m[1],'share':float(m[2])} for m in re.finditer(r'('+'|'.join(sorted(PREFS,key=len,reverse=True))+r')\((\d+(?:\.\d+)?)%\)',cells[1])]
   if not regions:continue
   plan=plans.setdefault(food['id'],{'regions':[]})
   plan['seasonalRegions']=regions;plan['seasonalSourceUrl']=url
   plan['seasonalBasis']=(f'{2018+int(period[1])}年{period[2]}月の入荷シェア' if period else '資料に記載された同月の入荷シェア')+'（収穫量シェアではありません）'
def main():
 from update_data import DATA,save
 obj=json.loads(DATA.read_text(encoding='utf-8'));prepare_plan(obj,dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date());save(obj)
if __name__=='__main__':main()
