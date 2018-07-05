$(document).ready(function() {
    var thumb = new FileReader();
    var sender = new FileReader();
    var tgt_cst = null;
    thumb.addEventListener("loadstart", function() {
        if ($("#thumbnail > p").length)
            $("#thumbnail > p").remove();
        if ($("#thumbnail > img").length)
            $("#thumbnail > img").remove();
        $("#beforLoader").fadeIn(10);
    });
    thumb.addEventListener('load', function() {
        //$("#thumbnail").children("img").attr("src", thumb.result);
        $("#thumbnail").append('<img src="'+thumb.result+'">');
        $("#beforLoader").fadeOut();
    });

    
    if (window.File && window.FileReader) {
        console.log("File API is available");
    }else{console.log("File API is NOT available");}

    namespace = '/test';
    var hostname = document.location.hostname;
    console.log("hostname:"+hostname);
    if (hostname == "localhost" || hostname == "127.0.0.1" || hostname == "") {
        var socket = io('http://127.0.0.1:5000' + namespace);
    } else {
        var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);
    }
    console.log(socket);
    
    socket.on('connect', function() {
        console.log("connect");
        $(".progressbar").val(0);
        socket.emit('my_event', {data: "Checked connection"});
    });
    socket.on('my_response', function(msg) {
        $("#log").append('<br>' + $('<div/>').text('Received: ' + msg.data).html());
    });
    // 星座検出時の進捗表示
    socket.on('searching', function(msg){
        $("#searchBar").val(msg.data);
        if ($("#searchBar").val() == Number($("#searchBar").attr("max"))) {
            $("#result").empty();
            $(".theater").empty();
            $("#afterLoader").fadeIn(10);
        }
    });
    // 画像選択時に表示
    $('#image_data').change(function(){
        thumb.readAsDataURL(this.files[0]);
    });
    // 探すボタン押下時
    $("form#toServer").submit(function(event) {
        if (thumb.result == null) {
            alert("画像を指定してください");
        } else if (tgt_cst == null) {
            alert("星座を指定してください"); 
        }else if (hostname.disconnected == true) {
            //うまくできない
            alert("サーバーとの接続に失敗しました\nページを再読み込みしてください");
        } else {
            $("#log").append('<br>' + $('<div/>').text("send").html());
            console.log("push")
            socket.emit('push_send');            
        }
        return false;        
    });
    socket.on('session_id', function(msg) {
        var postData = {"image": thumb.result, "cst": tgt_cst};
        $.post(location.href + "/send/" + msg.id, postData)
        .done(function(data) {
            console.log(data)
            if(data == "failed") {
                alert("不正なセッションです");
            }else if (data == "successed") {
                console.log("success");
            }
        })
        .fail(function(data) {
            console.log("fail");
        });
    });
    socket.on("process_finished", function(msg) {
        $("#afterLoader").fadeOut();
        $(".theater").append('<img src="'+msg.img+'">');
        $("#result").append('<a href="javascript:void(0);" onclick="onClickImage();"><img src="'+msg.img+'"></a>');
    });
    //モーダルウインドウ
    $(".openModal").click(function() {
        var navClass = $(this).attr("class"),
            href = $(this).attr("href");
            $(href).fadeIn();
        $(this).addClass("open");
        return false;
    });
    $(".overLay").click(function(){
        $(this).parents(".modal").fadeOut();
        $(".openModal").removeClass("open");
        return false;
    });
    $(".constellationList").click(function(){
        id = $(this).attr("id");
        tgt_cst = id;
        $("#selectConstellation").empty().append(
            "<img id=\"tmpConstellation\" src=\"/static/" + id + ".svg\" style=\"object-fit:contain\">");
        deSVG('#tmpConstellation', true);
        $(this).parents(".modal").fadeOut();
        $(".openModal").removeClass("open");
        return false;
    });
    $(".constellationList").hover(function() {
        $(this).children("span").fadeIn();
        $(this).children("img").animate({
            opacity: 0.5
        });
    }, function() {
        $(this).children("span").fadeOut();
        $(this).children("img").animate({
            opacity: 1
        });
    })

    //sender.html ************************************************************************
    var contentFileName;
    $("#content > #content_image").change(function() {
        sender.readAsDataURL(this.files[0]);
        contentFileName = this.files[0].name;
    });
    $("form#content").submit(function(event) {
        var text = $(this).children("#content_message").val();
       if (text == "") {
           alert("1を入力してください");
       }else{
            $(".loading").fadeIn();
            if (sender.result == undefined) {
                sender.result = null;
                contentFileName = null;
            }
            socket.emit('content_push', {content: text, file: sender.result, file_name: contentFileName});
       }
       return false;
    });
    socket.on("send_complete", function(msg){
        $(".loading").fadeOut();
        alert("メッセージが送信されました。ありがとうございます！");
    });
    
});

function resizeB64(b64img, callback) {
    const SIZE = 2000;
    var img = new Image();
    img.onload = function() {
        var canvas = document.createElement("canvas");
        var dstHeight, dstWidth;
        if (this.width > this.height) {
            dstWidth = SIZE;
            dstHeight = this.height * SIZE / this.width;
        } else {
            dstHeight = SIZE;
            dstWidth = this.width * SIZE / this.height;
        }
        canvas.width = dstWidth;
        canvas.height = dstHeight;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, dstWidth, dstHeight);
        callback(canvas.toDataURL("image/jpeg"));
    };
    img.src = b64img;
}

function onClickImage() {
    $(".theater").fadeIn();
    return false;
}

function onClickTheater() {
    $(".theater").fadeOut();
    return false;
}