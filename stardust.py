"""stardust 2017/10/21~"""
import numpy as np
import cv2
import time
import Constellation as cs
IMPORT_SOCKET = True
try:
    from flask_socketio import emit
except ImportError:
    IMPORT_SOCKET = False
SIZE = 666  # 画像サイズ(横)


class Stardust:
    def __init__(self, image_name,
                 star_num=120,
                 star_depth=10,
                 dist_max=50,  # 画像の大きさによるので固定すべきでなさそう
                 angle_max=5,
                 socket=None,
                 debug=False,
                 session=None
                 ):
        global IMPORT_SOCKET
        if isinstance(image_name, np.ndarray):  # 画像が直接渡された場合
            self.image = image_name
        else:
            self.image = cv2.imread(image_name)
        # 小さすぎたら拡大
        if max(self.image.shape[0], self.image.shape[1]) < 1200:
            self.image = self.scale_down(self.image, 
                                         max(self.image.shape[0],
                                             self.image.shape[1])/1200)
        self.text_size = (1.72e-7
                          * self.image.shape[0]
                          * self.image.shape[1]
                          + 1.34)  # TODO:adjust!
        self.text_weight = (3 if (self.image.shape[0] > 2000
                                  and self.image.shape[1] > 2000)
                            else 1)
        self.c_radius = int(max(self.image.shape[0], self.image.shape[1])/250)
        self.l_weight = int(max(self.image.shape[0], self.image.shape[1])/1000)
        self.star_num = star_num  # Param:取り出す星の数
        self.star_depth = star_depth  # Param:近隣探索数の上限
        self.dist_max = dist_max  # Param:許容する距離誤差の上限
        self.angle_max = angle_max  # Param:許容する角度誤差の上限
        self.likelihood = 0
        self.written_img = self.image.copy()
        if IMPORT_SOCKET:
            self.socket = socket
            self.session = session
        else:
            self.socket = None
        self.debug = debug
        # 画像の4隅
        self.a = np.array([0, 0])
        self.b = np.array([self.image.shape[1] - 1, 0])
        self.c = np.array([self.image.shape[1] - 1, self.image.shape[0] - 1])
        self.d = np.array([0, self.image.shape[0] - 1])
        self.standard_list = []  # 基準(始点から検知判定まで)の星 描画時再訪問用
        self.detect = None  # 見つかったかどうか(探索後bool)
        self.thr_min = 90
        self.thr_max = 220
        self.stars = self.__detect_stars()

    def get_image(self):
        return self.written_img

    def scale_down(self, img, scale):
        """入力画像をscale分の1に縮小"""
        hight = img.shape[0]
        width = img.shape[1]
        small = cv2.resize(img, (round(width/scale), round(hight/scale)))
        return small

    def darken(self, gamma):
        """ガンマ補正をかける　gammma < 1で暗くなる"""
        lut = np.ones((256, 1), dtype='uint8') * 0
        for i in range(256):
            lut[i][0] = 255 * pow(float(i) / 255, 1.0 / gamma)
        image_gamma = cv2.LUT(self.image, lut)
        self.image = image_gamma

    def __detect_stars(self):
        """最適(？)スレッショルドを設定し、抽出した星座標のリストを返す"""
        flag = True
        thr = self.thr_max

        # 画像から星情報(面積と座標)をget
        img_gray = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)
        self.del_img = self.image.copy()
        self.first_delete = True
        self.tmp_stars = []
        while True:
            thr, contours = self._thr_optimize(img_gray, thr)
            if contours is None:
                continue
            areas, stars = self._get_star_info(thr, contours)
            if stars is None:
                continue
            img_gray = self._delete_light_pollution(areas, stars, contours)
            if img_gray is not None:
                continue
            else:
                break

        # 星のうち明るいほうから順に取り出す
        r_areas_arg = np.argsort(areas)[::-1]  # 面積の大きい順にインデックスをリストに格納
        if len(stars) > self.star_num:
            astars = [stars[r_areas_arg[i]] for i in range(self.star_num)]
        else:
            astars = [stars[r_areas_arg[i]] for i in range(len(stars))]
            print("star num:", len(astars))

        # 光害の中にまきこまれた星があれば追加しておく
        for tmp_star in self.tmp_stars:
            # 半径円に含まれるくらい近くに星があればそれは追加しない
            flags = [True for star in astars
                     if np.linalg.norm(tmp_star-star) < self.c_radius]
            if not (True in flags):
                astars.append(tmp_star)
        print("star num:", len(astars))
        print("threashold:", thr)
        # DEBUG
        if self.debug:
            tmp = self.image.copy()
            for star in astars:
                cv2.circle(
                    tmp, (star[0], star[1]), 2, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.imshow("finalcnt",
                       self.scale_down(tmp,
                                       max(tmp.shape[0], tmp.shape[1])/SIZE))
            cv2.waitKey(1)

        return astars

    def on_mouse(self, event, x, y, flag, param):
        """マウスクリック時"""
        # 左クリックで最近傍の星出力
        if event == cv2.EVENT_LBUTTONDOWN:
            print("mouse:", x, y, sep=' ', end='\n')
            print(self.search_near_star((x, y), 0))

    def search_near_star(self, p, i, return_num=1):
        """
        (x, y)にi番目(0オリジン)に近いものを返す
        return_numで複数取得できる
        """
        if i + return_num - 1 >= len(self.stars):
            print("Can't detect")
            return None

        L = [np.linalg.norm(star-p) for star in self.stars]
        index = np.array(L)
        index = np.argsort(index)
        if return_num == 1:
            return self.stars[index[i]]
        elif return_num > 1:
            return [self.stars[index[i+e]] for e in range(return_num)]

    def draw_line(self,
                  constellation,
                  mode=cs.DEFAULT,
                  predict_circle=False,
                  write_text=False):
        self.predict_circle = predict_circle
        if isinstance(constellation, list):
            detect_flags = []
            for cst in constellation:
                ret = self.draw_line(cst,
                                     mode=mode,
                                     predict_circle=predict_circle,
                                     write_text=write_text)
                detect_flags.append(ret)
            if True in detect_flags:
                return True
            else:
                return False
        if mode == cs.DEFAULT:
            line = constellation.line
        elif mode == cs.IAU:
            line = constellation.iau
        self.constellation = constellation

        min_like = 0
        best_point = None
        sockcnt = 0
        # 検出した星のうちself.star_num個すべてについてみていく
        for star in self.stars:
            if self.socket is not None:
                emit('searching', {"data": sockcnt}, room=self.session, namespace="/test")
                sockcnt += 1
                self.socket.sleep(0)
            self.std_star = star
            # 基準星の近くのself.star_depth個をとってくる
            second_candidates = self.search_near_star(
                star, 0, return_num=self.star_depth)
            # とってきた二番目の星候補すべてについて、残りの星を探索し星座一致率を計算
            for second in second_candidates:
                self.second_star = second
                self.likelihood, self.star_count = 0, 1
                ret = self.__search_constellation(
                    0, second, second - self.std_star, line)
                correct_probability = self.likelihood / line["MAX"]
                if ret == line["MAX"] or correct_probability > 0.8:  # 全部見つかったら
                    # 1つめと2つめについて描く
                    if self.debug:
                        print(self.std_star,
                              self.star_count,
                              round(correct_probability * 100, 2),
                              "%")
                    self.star_count = 0
                    p_list = [star, second]
                    sp, ep = self.__line_adjust(star, second)
                    cv2.line(self.written_img,
                             sp,
                             ep,
                             (255, 255, 255),
                             self.l_weight,
                             cv2.LINE_AA)
                    for p in p_list:
                        cv2.circle(self.written_img, 
                                   (p[0], p[1]),
                                   self.c_radius,
                                   (255, 255, 255),
                                   self.l_weight,
                                   cv2.LINE_AA
                                   )
                    # 残りについて書く
                    self.__search_constellation(0,
                                                second,
                                                second - self.std_star,
                                                line, write=True,
                                                predict_write=True)
                    if write_text:  # 文字入れありの場合
                        cv2.putText(self.written_img,
                                    constellation.en_name,
                                    (self.std_star[0] + 4 * self.c_radius,
                                        self.std_star[1] - 4 * self.c_radius),
                                    cv2.FONT_HERSHEY_SCRIPT_COMPLEX,
                                    self.text_size,
                                    (255, 255, 255),
                                    self.text_weight,
                                    cv2.LINE_AA  # 太さをマネージする(星座の大きさの計算が必要…？)
                                    )
                    if self.socket is not None:
                        emit('searching', {"data": self.star_num-1}, room=self.session, namespace="/test")
                        self.socket.sleep(0)
                    print(constellation.en_name, "wrote.")
                    self.detect = True
                    return self.detect

                elif correct_probability > 0.5:
                    if self.debug:
                        print(self.std_star,
                              self.star_count,
                              round(correct_probability * 100, 2),
                              "%")
                    # 星座の一致率が高いものを保存しておく
                    if min_like < correct_probability:
                        min_like = correct_probability
                        best_point = [star, second]
                elif self.debug and self.star_count > line["N"]:
                    print(self.std_star,
                          self.star_count,
                          round((self.likelihood / line["MAX"]) * 100, 2),
                          "%")

        self.star_count = 0
        # 星座一致率がある程度高いものが保存されていた場合、描く
        if best_point is None:
            print("failed to detect", constellation.en_name)
            self.detect = False
            return self.detect
        else:
            self.std_star = best_point[0]
            self.second_star = best_point[1]
            # 一個目と二個目を描く
            sp, ep = self.__line_adjust(best_point[0], best_point[1])
            cv2.line(self.written_img,
                     sp,
                     ep,
                     (255, 255, 255),
                     self.l_weight,
                     cv2.LINE_AA)
            for p in best_point:
                cv2.circle(self.written_img,
                           (p[0], p[1]),
                           self.c_radius,
                           (255, 255, 255),
                           self.l_weight,
                           cv2.LINE_AA
                           )
            # 残りを描く
            self.__search_constellation(0,
                                        best_point[1],
                                        best_point[1] - best_point[0],
                                        line,
                                        write=True,
                                        predict_write=True
                                        )
            if write_text:
                cv2.putText(self.written_img,
                            constellation.en_name,
                            (self.std_star[0] + 4 * self.c_radius,
                                self.std_star[1] - 4 * self.c_radius),
                            cv2.FONT_HERSHEY_SCRIPT_COMPLEX,
                            self.text_size,
                            (255, 255, 255),
                            self.text_weight,
                            cv2.LINE_AA  # 太さをマネージする(星座の大きさの計算が必要…？)
                            )
            print(constellation.en_name, "wrote.")
            self.detect = True
            return self.detect

    def __search_constellation(self, count, point, bector, constellation, write=False, predict_write=False, next_one=False):
        """(何番目の星か, 前の点, 前のベクトル, 星座(の一部))"""
        dist, ang = constellation["D"][count], constellation["ANGS"][count]
        if ang is None:
            if write and len(self.standard_list) > dist:
                re_point = self.standard_list[dist]
                self.__write(point, re_point)

                if count+1 == len(constellation["D"]):
                    if "BP" in constellation and len(constellation["BP"]) > 0:
                        for (branch, rest) in zip(
                                constellation["BP"], constellation["REST"]):
                            self.__search_constellation(0,
                                                        branch,
                                                        near_predict - point,
                                                        rest,
                                                        write=write,
                                                        predict_write=predict_write
                                                        )
                    return self.star_count
                return self.__search_constellation(count+1,
                                                   re_point,
                                                   re_point - point,
                                                   constellation,
                                                   write=write,
                                                   predict_write=predict_write
                                                   )
            else:
                return self.star_count

        # 星座データから予測される次の星の位置をpredictに格納
        predict = point + self.__rotate_bector(bector, ang) * dist
        # predictの最近傍とそのつぎに近い星を取得
        near_predict, else_predict = self.search_near_star(
            predict, 0, return_num=2)
        predict_diff = np.linalg.norm(near_predict - predict)
        theta = self.__calc_angle(bector, near_predict - point)
        if next_one:  # 次の星の予測誤差を返す
            return abs(abs(ang) - theta)

        else_diff = np.linalg.norm(else_predict - predict)
        else_theta = self.__calc_angle(bector, else_predict - point)
        if (count + 1 < len(constellation["D"])
                and else_diff < self.dist_max
                and abs(abs(ang) - else_theta) < self.angle_max):
            # 二つの近傍の星について、その先にそれっぽいのがあるほうを採用する
            prds = [near_predict, else_predict]
            errs = [(predict_diff, theta), (else_diff, else_theta)]
            angle_diffs = [
                self.__search_constellation(
                    count+1,
                    e,
                    e-point,
                    constellation,
                    next_one=True) for e in prds]
            i = np.argmin(angle_diffs)
            near_predict = prds[i]
            predict_diff, theta = errs[i]

        # もし予想地点近く(近くとは)に星があれば
        if (predict_diff < self.dist_max
                and abs(abs(ang) - theta) < self.angle_max):
            # 尤度の計算
            found_bec_rate = (np.linalg.norm(near_predict - point)
                              / np.linalg.norm(bector))
            err = (abs(dist - found_bec_rate)
                   if abs(dist - found_bec_rate) < 1 else 1)
            self.likelihood += 1 - err / dist

            if count == 0 and (-2 in constellation["JCT"]
                               or -1 in constellation["JCT"]):
                # 基準点、二番点の処理
                for i in range(constellation["JCT"].count(-2)):
                    constellation["BP"].append(self.std_star)
                for i in range(constellation["JCT"].count(-1)):
                    constellation["BP"].append(self.second_star)
            if count in constellation["JCT"]:  # 現在の点が分岐点なら
                for i in range(constellation["JCT"].count(count)):
                    constellation["BP"].append(near_predict)
            self.star_count += 1
            if write:
                if "N" in constellation:
                    if len(self.standard_list) == 0:
                        self.standard_list += [self.std_star, self.second_star]
                    self.standard_list.append(near_predict)
                self.__write(point, near_predict)

            if count+1 == len(constellation["D"]):  # 端点ならば
                if "BP" in constellation and len(constellation["BP"]) > 0:
                    # 分岐点が存在すれば
                    for (branch, rest) in zip(
                            constellation["BP"], constellation["REST"]):
                        self.__search_constellation(0,
                                                    branch,
                                                    near_predict - point,
                                                    rest,
                                                    write=write,
                                                    predict_write=predict_write
                                                    )

                return self.star_count
            return self.__search_constellation(count+1,
                                               near_predict,
                                               near_predict - point,
                                               constellation,
                                               write=write,
                                               predict_write=predict_write
                                               )
        elif (predict_write and write):  # 予想描画機能オンのとき
            predict[0, 0] = int(predict[0, 0])
            predict[0, 1] = int(predict[0, 1])
            predict = np.array(predict.tolist())[0]
            # 予測点がはみ出すとき
            if ((predict[0] < 0 or predict[0] >= self.image.shape[1])
                    or (predict[1] < 0 or predict[1] >= self.image.shape[0])):
                # TODO: はみ出した点が分岐点だった場合の処理
                managed_predict = self.__manage_cross(point, predict)
                print("managed:", managed_predict)
                if managed_predict is not None:
                    sp, ep = self.__line_adjust(point, managed_predict)
                    cv2.line(self.written_img,
                             sp,
                             ep,
                             (255, 255, 255),
                             self.l_weight,
                             cv2.LINE_AA)
                if count+1 == len(constellation["D"]):  # 端点ならば
                    if "BP" in constellation and len(constellation["BP"]) > 0:
                        # 分岐点が存在すれば
                        for (branch, rest) in zip(
                                constellation["BP"], constellation["REST"]):
                            self.__search_constellation(0,
                                                        branch,
                                                        predict - point,
                                                        rest,
                                                        write=True,
                                                        predict_write=True
                                                        )

                    return self.star_count

                return self.__search_constellation(count+1,
                                                   predict,
                                                   predict - point,
                                                   constellation,
                                                   write=True,
                                                   predict_write=True
                                                   )

            if count == 0 and (-2 in constellation["JCT"]
                               or -1 in constellation["JCT"]):  # 基準点、二番点の処理
                for i in range(constellation["JCT"].count(-2)):
                    constellation["BP"].append(self.std_star)
                for i in range(constellation["JCT"].count(-1)):
                    constellation["BP"].append(self.second_star)  # なんとかしたつもり
            if count in constellation["JCT"]:  # 現在の点が分岐点なら
                for i in range(constellation["JCT"].count(count)):
                    constellation["BP"].append(predict)

            self.__write(point, predict, circle=self.predict_circle)

            if count+1 == len(constellation["D"]):
                # 端点ならば TODO:端点いかなくても分岐点は書きたい→前の辺を参照する現状では厳しい
                if len(constellation["BP"]) > 0:  # 分岐点が存在すれば
                    for (branch, rest) in zip(
                            constellation["BP"], constellation["REST"]):
                        self.__search_constellation(0,
                                                    branch,
                                                    predict - point,
                                                    rest,
                                                    write=True,
                                                    predict_write=True
                                                    )

                return self.star_count
            return self.__search_constellation(count+1,
                                               predict,
                                               predict - point,
                                               constellation,
                                               write=True,
                                               predict_write=True
                                               )
        else:  # 近くに星がなければ
            constellation["BP"].clear()
            return self.star_count

    def __line_adjust(self, start, end):
        """線分を円周の部分までで止めるような始点、終点を返す"""
        b = end - start
        b = b / np.linalg.norm(b)
        restart = start + b * self.c_radius

        b = start - end
        b = b / np.linalg.norm(b)
        reend = end + b * self.c_radius
        return ((int(restart[0]), int(restart[1])), (int(reend[0]), int(reend[1])))

    def __rotate_bector(self, bector, deg):
        """bector を deg 度だけ回転する"""
        rad = np.deg2rad(deg)
        cos = np.cos(rad)
        sin = np.sin(rad)
        R = np.matrix((
            (cos, -sin),
            (sin, cos)
        ))
        return R @ bector

    def __calc_angle(self, bec_a, bec_b):
        """2つのベクトルのなす角を求める"""
        dot = bec_a @ bec_b
        cos = dot / (np.linalg.norm(bec_a) * np.linalg.norm(bec_b))
        rad = np.arccos(cos)
        return np.rad2deg(rad)

    def __check_cross(self, p1, p2, p3, p4):
        """ベクトル同士が交差していればTrue, else Falseを返す"""
        t1 = (p1[0] - p2[0]) * (p3[1] - p1[1]) + (p1[1] - p2[1]) * (p1[0] - p3[0])
        t2 = (p1[0] - p2[0]) * (p4[1] - p1[1]) + (p1[1] - p2[1]) * (p1[0] - p4[0])
        t3 = (p3[0] - p4[0]) * (p1[1] - p3[1]) + (p3[1] - p4[1]) * (p3[0] - p1[0])
        t4 = (p3[0] - p4[0]) * (p2[1] - p3[1]) + (p3[1] - p4[1]) * (p3[0] - p2[0])
        return t1 * t2 < 0 and t3 * t4 < 0

    def __write(self, previous, current, circle=True):
        sp, ep = self.__line_adjust(previous, current)
        cv2.line(self.written_img,
                 sp,
                 ep,
                 (255, 255, 255),
                 self.l_weight,
                 cv2.LINE_AA)
        if circle:
            cv2.circle(self.written_img,
                       (current[0], current[1]),
                       self.c_radius,
                       (255, 255, 255),
                       self.l_weight,
                       cv2.LINE_AA
                       )

    def __manage_cross(self, start, end):
        """はみ出た点に対し、そこに続くような線を描くための枠上の座標を返す"""
        # TODO: 外から中へのクロスへの対処
        if self.__check_cross(start, end, self.a, self.b):
            print("0")
            a = start[1]
            deg = self.__calc_angle(end - start, self.b - self.a)
            if deg > 90:
                deg = 180 - deg
                x = a // np.tan(np.deg2rad(deg))
                return np.array([start[0] - x, 0])
            else:
                x = a // np.tan(np.deg2rad(deg))   
                return np.array([start[0] + x, 0])
        elif self.__check_cross(start, end, self.b, self.c):
            print("1")
            a = self.c[0] - start[0]
            deg = self.__calc_angle(end - start, self.c - self.b)
            if deg > 90:
                deg = 180 - deg
                x = a // np.tan(np.deg2rad(deg))
                return np.array([self.b[0], start[1] - x])
            else:
                x = a // np.tan(np.deg2rad(deg))
                return np.array([self.b[0], start[1] + x])
        elif self.__check_cross(start, end, self.c, self.d):
            print("2")
            a = self.d[1] - start[1]
            deg = self.__calc_angle(end - start, self.d - self.c)
            if deg > 90:
                deg = 180 - deg
                x = a // np.tan(np.deg2rad(deg))
                return np.array([start[0] - x, self.c[1]])
            else:
                x = a // np.tan(np.deg2rad(deg))
                return np.array([start[0] + x, self.c[1]])
        elif self.__check_cross(start, end, self.d, self.a):
            print("3")
            a = start[0]
            deg = self.__calc_angle(end - start, self.a - self.d)
            if deg > 90:
                deg = 180 - deg
                x = a // np.tan(np.deg2rad(deg))
                return np.array([0, start[1] + x])
            else:
                x = a // np.tan(np.deg2rad(deg))
                return np.array([0, start[1] - x])

    def _thr_optimize(self, gray_img, thr):
        _, bin_img = cv2.threshold(gray_img, thr, 255, cv2.THRESH_BINARY)
        if self.debug:
            cv2.imshow("gray",
                       self.scale_down(bin_img,
                                       max(bin_img.shape[0],
                                           bin_img.shape[1])/666))
            cv2.waitKey(1)

        _, contours, _ = cv2.findContours(
            bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if thr == self.thr_max:
            self.first_starnum = len(contours)

        if thr == self.thr_min:
            return (thr, contours)
        elif len(contours) < 80:
            for cnt in contours:
                M = cv2.moments(cnt)
                if M['m00'] != 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    self.tmp_stars.append(np.array([cx, cy], dtype='int32'))
                else:
                    self.tmp_stars.append(np.array(cnt[0, 0], dtype='int32'))
            thr -= 10
            return (thr, None)
        elif len(contours) < 400:
            thr -= 10
            return (thr, None)
        else:
            return (thr, contours)

    def _get_star_info(self, thr, contours):
        areas, stars = [], []
        for cnt in contours:
            M = cv2.moments(cnt)
            areas.append(M["m00"])
            if M["m00"] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                stars.append(np.array([cx, cy], dtype='int32'))
            else:
                stars.append(np.array(cnt[0, 0], dtype='int32'))

        if (np.median(areas) == 0 and
                len(contours) < self.first_starnum * 4 and
                thr != self.thr_min):
            thr -= 10
            return (thr, None)

        return (areas, stars)

    def _delete_light_pollution(self, areas, stars, contours):
        max_a = np.argmax(areas)
        if self.first_delete:
            self.first_delete = False
            self.delete_count = 0
            self.area_std = np.std(areas)
            if self.debug:
                print("std:", self.area_std)
        if self.area_std > 100 and areas[max_a] > 2.5 * self.area_std:
            cnt = contours[max_a]
            M = cv2.moments(cnt)
            cx = int(M['m10'] / M['m00'])
            cy = int(M['m01'] / M['m00'])
            self.tmp_stars.append(np.array([cx, cy], dtype='int32'))
            self.del_img = cv2.fillConvexPoly(self.del_img, cnt, (255, 0, 0))
            self.delete_count += 1
            if self.delete_count > 10:
                return None
            img_gray = cv2.cvtColor(self.del_img, cv2.COLOR_RGB2GRAY)
            if self.debug:
                cv2.imshow("deleted",
                    self.scale_down(self.del_img, max(self.del_img.shape[0], self.del_img.shape[1])/666))
                cv2.waitKey(1)
            return img_gray
        else:
            return None


if __name__ == '__main__':
    #test, 0004, 0038, 1499, 1618, 1614, 1916, g001 ~ g004, dzlm, dalr, daqw
    IMAGE_FILE = "0038"
    f = "source\\" + IMAGE_FILE + ".JPG"
    start = time.time()
    sd = Stardust(f, debug=True)
    cst = cs.sgr
    sd.draw_line(cst)
    #sd.draw_line(cs.sco)
    end = time.time()
    print("elapsed:", end - start)
    print(sd.detect)
    ret = sd.get_image()
    cv2.namedWindow("return", cv2.WINDOW_NORMAL)
    cv2.imshow("return", ret)
    cv2.setMouseCallback("return", sd.on_mouse)
    #cv2.imwrite(cst.short_name+"_"+IMAGE_FILE+".JPG", ret)
    #cv2.imwrite("multi_"+IMAGE_FILE+".JPG", ret)
    cv2.waitKey()