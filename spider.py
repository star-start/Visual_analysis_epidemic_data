import time
import traceback
import requests
import hashlib
from pprint import pprint
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pymysql import connect

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
}


def get_conn():
    # 用于获取MySQL的链接对象
    conn = connect(
        user='root',
        password='254689',
        database='covid19',
        host='127.0.0.1',
        charset='utf8'
    )
    # 得到游标对象，只有游标对象可以执行sql语句
    cursor = conn.cursor()
    return conn, cursor


def cal_limit_days(month=3):
    # 获取完整月份数据,现在的代码默认获取3个月数据
    now = datetime.now()  # 获取今天的日期
    # 计算month个月前的日期
    pre_date = now - relativedelta(months=month)
    # print(pre_date) #2022-09-07 14:26:30.839619
    res_date = datetime(pre_date.year, pre_date.month, 1)  # 相当于获取2022-09-01
    # 计算两个日期相差多少天
    diff_day = (now - res_date).days  # days参数用于查看相差多少天
    return diff_day + 1, res_date  # diff_day加了1是保险作用


def turn_to_sql_date(year, date, min_date):
    # 判断日期界限并转化为mysql支持的日期格式
    ds = year + '.' + date  # 传入的数据  year是年  date是月和日
    #
    ds_tmp = datetime.strptime(ds, '%Y.%m.%d')
    if ds_tmp < min_date:
        print(f'{ds_tmp.date()}日期超过最小边界，跳过！')
        return None
    return ds.replace('.', '-')


def get_tencent_data():
    # 获取国内疫情信息
    limit, min_date = cal_limit_days()
    print("-----------------正在获取全国疫情信息-----------------")
    print(f'当前limit值为:{limit}  最小日期界限为:{min_date.date()}')
    contry_url = 'https://api.inews.qq.com/newsqa/v1/query/inner/publish/modules/list?modules=chinaDayListNew,chinaDayAddListNew&limit=' + str(
        limit)
    con_resp = requests.get(url=contry_url, headers=headers)
    china_data = con_resp.json()['data']
    # 按照日期来整理全国疫情数据
    history = {}  # 保存数据的字典
    for i in china_data['chinaDayAddListNew']:
        ds = turn_to_sql_date(i['y'], i['date'], min_date)  # 日期，后续要转为2022-11-06或2022/11/06
        if not ds:  # 如果为None则跳过当前日期
            continue
        # 添加疫情信息数据
        history[ds] = {
            'confirm_add': i['confirm'],
            'heal_add': i['heal'],
            'dead_add': i['dead'],
            'importedCase_add': i['importedCase']
        }
    for i in china_data['chinaDayListNew']:
        ds = turn_to_sql_date(i['y'], i['date'], min_date)  # 日期，后续要转为2022-11-06或2022/11/06
        if not ds:  # 如果为None则跳过当前日期
            continue
        if ds not in history:  # 检查日期是否存在于上述的字典中，仅当日期存在才执行写入
            continue
        # 更新已经存在的日期的记录
        history[ds].update({
            'confirm': i['confirm'],
            'confirm_now': i['nowConfirm'],
            'heal': i['heal'],
            'dead': i['dead'],
            'importedCase': i['importedCase']
        })

    insert_into_history(history)


def get_provice_data():
    # 获取省份的信息
    limit, min_date = cal_limit_days()
    # 这是接口一的url
    ad_url = 'https://api.inews.qq.com/newsqa/v1/query/inner/publish/modules/list?modules=localCityNCOVDataList,diseaseh5Shelf'
    ad_resp = requests.get(url=ad_url, headers=headers)
    china_pros = ad_resp.json()['data']['diseaseh5Shelf']['areaTree'][0]['children']

    # 添加港澳台的数据
    adcode_dict = {'台湾': '710000', '香港': '810000', '澳门': '820000'}
    # print(adcode_dict)
    # 最新的数据以接口一为准，历史数据以接口三为准
    for info in china_pros:
        province = info['name']
        adcode = info['adcode']
        today = info['today']
        total = info['total']
        ds_str = info['date'].replace('/', '-')
        # 整理最新一天数据
        insert_into_details([ds_str, province, total['confirm'], today['confirm'], total['nowConfirm'],
                             None, total['heal'], total['dead'], today['dead_add']])

        # 获取省份的历史信息，记得港澳台的adcode是不存在的
        if adcode == '':
            adcode = adcode_dict[province]
        # 这是接口三的url
        provice_url = f'https://api.inews.qq.com/newsqa/v1/query/pubished/daily/list?adCode={adcode}&limit={limit}'
        pro_resp = requests.get(url=provice_url, headers=headers)
        # 获取当前省份的数据
        pro_data = pro_resp.json()['data']
        for data in pro_data:
            update_time = turn_to_sql_date(str(data['year']), data['date'], min_date)
            if not update_time:
                continue
            # 将每天的数据整合到一个列表中
            insert_into_details([update_time, province, data['confirm'], data['newConfirm'], None,
                                 data['newHeal'], data['heal'], data['dead'], data['newDead']])


def gen_code():
    t = str(int(time.time()))
    r = "23y0ufFl5YxIyGrI8hWRUZmKkvtSjLQA"
    s = "123456789abcdefg"

    crypt_str = t + r + s + t

    # 使用hashlib完成加密流程
    s1 = hashlib.sha256()
    s2 = hashlib.sha256()
    # 使用加密对象的update方法即可进行加密，注意加密的字符串要转为字节码即Bytes类型
    s1.update(crypt_str.encode())

    # 获取加密的字符串,并让其大写
    data_code = s1.hexdigest().upper()  # .upper()就是让其大写的方法
    # Header中的signature
    crypt_str2 = t + "fTN2pfuisxTavbTuYVSsNJHetwq5bJvCQkjjtiLM2dCratiA" + t
    s2.update(crypt_str2.encode())
    headers_code = s2.hexdigest().upper()
    return t, data_code, headers_code


def get_risk_data():
    '''获取全国高低风险区域的信息'''
    t, data_code, headers_code = gen_code()
    risk_url = 'http://bmfw.www.gov.cn/bjww/interface/interfaceJson'
    headers.update({
        "Host": "bmfw.www.gov.cn",
        "Origin": "http://bmfw.www.gov.cn",
        "Referer": "http://bmfw.www.gov.cn/yqfxdjcx/risk.html",
        "x-wif-nonce": "QkjjtiLM2dCratiA",
        "x-wif-paasid": "smt-application",
        "x-wif-signature": headers_code,
        "x-wif-timestamp": t
    })
    # 构建请求参数
    data = {
        "key": "3C502C97ABDA40D0A60FBEE50FAAD1DA",
        "appId": "NcApplication",
        "paasHeader": "zdww",
        "timestampHeader": t,
        "nonceHeader": "123456789abcdefg",
        "signatureHeader": data_code
    }
    risk_resp = requests.post(url=risk_url, headers=headers, json=data)
    # print(risk_resp.status_code)
    # print(risk_resp.json())
    if risk_resp.status_code == 200:
        risk_data = risk_resp.json()['data']
        utime = risk_data['end_update_time']  #
        # 高低风险地区表分开，然后整合
        h_risk = risk_data['highlist']
        l_risk = risk_data['lowlist']
        combine_risk = zip(('高风险', '低风险'), (h_risk, l_risk))

        # 列表保存结果
        res_data = []
        for risk_type, risk_list in combine_risk:
            for rlist in risk_list:
                province = rlist['province']
                city = rlist['city']
                county = rlist['county']
                for address in rlist['communitys']:
                    res_data.append([utime, province, city, county, address, risk_type])
        insert_into_risk(res_data)


def insert_into_risk(data):
    conn, cursor = get_conn()
    try:
        # risk_area表中需要输入的字段有6个,因为是以id自增为主键所以要这样写
        sql = """insert into risk_area(end_update_time,province,city,county,address,type)
              values(%s,%s,%s,%s,%s,%s)"""
        # 查询某个日期的数据是否存在
        sql_query = "select %s = (select end_update_time from risk_area order by id desc limit 1)" #order by id desc limit 1的意思是按id进行降序排列并限制只取第一条
        cursor.execute(sql_query, data[0][0])
        if not cursor.fetchone()[0]:  # fetchone()的用法是：返回单个的元组如('id','title')，也就是一条记录(row)，如果没有结果 则返回 None
            for item in data:
                cursor.execute(sql, item)
                print("成功写入:", " ".join(item))
                # 提交事务，注意，如果不写这句，sql中更新不会被执行
                conn.commit()
        else:
            print("当前已经是最新数据，无需更新！")
    except:  # 异常处理，数据库一般会进行回滚
        conn.rollback()  # 回滚数据库
        traceback.print_exc()  # 打印详细的错误信息
    finally:  # 关闭连接
        cursor.close()
        conn.close()


def insert_into_history(data):
    # 写入到history表中
    conn, cursor = get_conn()
    print(f'开始更新全国疫情信息...')
    try:
        # history表中需要输入的字段有10个
        sql = "insert into history values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        # 查询某个日期的数据是否存在
        sql_query = "select confirm from history where ds = %s"
        # k=时间  ,v=9个字段的数据
        for k, v in data.items():  # items将键值对进行拆分
            if not cursor.execute(sql_query, k):  # .execute()的作用是执行一条SQL语句
                cursor.execute(sql, [k, v.get('confirm'), v.get('confirm_add'), v.get('confirm_now'),
                                     v.get('heal'), v.get('heal_add'), v.get('dead'),
                                     v.get('dead_add'), v.get('importedCase'), v.get('importedCase_add')])
                print(f'[history] | [{k}] 记录写入成功！')
        # 提交事务，注意，如果不写这句，sql中更新不会被执行
        conn.commit()
    except:  # 异常处理，数据库一般会进行回滚
        conn.rollback()  # 回滚数据库
        traceback.print_exc()  # 打印详细的错误信息
    finally:  # 关闭连接
        cursor.close()
        conn.close()


def insert_into_details(data):
    # 写入到details表中
    conn, cursor = get_conn()
    try:
        # details表中需要输入的字段有9个，因为是以id自增为主键所以要这样写
        sql = """
                insert into details(update_time, province, confirm,
                confirm_add, confirm_now, heal_add, heal, dead, dead_add)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
        # 查询某个日期的数据是否存在
        sql_query = "select confirm from details where update_time = %s and province = %s "
        if not cursor.execute(sql_query, [data[0], data[1]]):  # .execute()的作用是执行一条SQL语句
            cursor.execute(sql, data)
            print(f'写入[{data[1]}] | [{data[0]}]成功！')
            # 提交事务，注意，如果不写这句，sql中更新不会被执行
            conn.commit()
    except:  # 异常处理，数据库一般会进行回滚
        conn.rollback()  # 回滚数据库
        traceback.print_exc()  # 打印详细的错误信息
    finally:  # 关闭连接
        cursor.close()
        conn.close()


def main():
    get_tencent_data()
    get_provice_data()
    get_risk_data()


if __name__ == '__main__':
    main()


# 20大数据2班 09 陈子欣